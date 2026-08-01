"""Persisted navigation state: pins, and per-file/per-symbol frecency.

One SQLite database under RONIN_CACHE_DIR. SQLite is here for what it removes: no
lock file, no temp-file-and-rename dance, no tolerant JSON parsing, no
read-whole-document-to-change-one-counter. A write is a statement, concurrent
writers wait their turn (busy_timeout) instead of racing, and the rankings are
ORDER BY instead of Python sorts over dictionaries.

  files      visit and edit counts, and the position last seen in each file.
             Feeds the sidebar's Trail and the file picker's ordering.
  symbols    per-(file, symbol) visit counts. Feeds the sidebar's Symbols
             section and the ordering of symbol candidates. Keyed on the pair
             because same-named symbols in different files (many `handle`s, many
             `__init__`s) are genuinely different jump targets.
  co_visits  how often a jump went from one file to another, which is what makes
             a second goto-definition from the same file land better than the
             first.
  pins       user-curated slots. Slot N stays slot N -- that is what makes
             `space N` muscle memory, unlike frecency, where rankings shift. A
             pin's line/col follows the user's last save in that file
             (Harpoon-style: you come back to where you left off).

WAL mode is deliberate twice over: writers never block the sidebar's reads, and
every commit touches state.db-wal, which is the file the sidebar watches to know
it should redraw.
"""

import contextlib
import json
import sqlite3
import time
from pathlib import Path

from config import NUM_PIN_SLOTS, RONIN_CACHE_DIR, STATE_DB

# Recency multiplier, as SQL: < 1h → 1.0, < 6h → 0.8, < 24h → 0.6, < 7d → 0.4,
# < 30d → 0.2, else 0.1. :now comes from the caller so every row in one query is
# scored against the same instant.
_DECAY = """
    CASE
        WHEN (:now - last_ts) / 3600.0 < 1   THEN 1.0
        WHEN (:now - last_ts) / 3600.0 < 6   THEN 0.8
        WHEN (:now - last_ts) / 3600.0 < 24  THEN 0.6
        WHEN (:now - last_ts) / 3600.0 < 168 THEN 0.4
        WHEN (:now - last_ts) / 3600.0 < 720 THEN 0.2
        ELSE 0.1
    END
"""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path      TEXT    PRIMARY KEY,
    visits    INTEGER NOT NULL DEFAULT 0,
    edits     INTEGER NOT NULL DEFAULT 0,
    last_ts   REAL    NOT NULL DEFAULT 0,
    last_line INTEGER NOT NULL DEFAULT 1,
    last_col  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS symbols (
    file    TEXT    NOT NULL,
    symbol  TEXT    NOT NULL,
    visits  INTEGER NOT NULL DEFAULT 0,
    last_ts REAL    NOT NULL DEFAULT 0,
    line    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (file, symbol)
);
CREATE TABLE IF NOT EXISTS co_visits (
    from_file TEXT    NOT NULL,
    to_file   TEXT    NOT NULL,
    count     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (from_file, to_file)
);
CREATE TABLE IF NOT EXISTS pins (
    slot INTEGER PRIMARY KEY,
    file TEXT    NOT NULL,
    line INTEGER NOT NULL DEFAULT 1,
    col  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

_ready = False


@contextlib.contextmanager
def _db():
    """A connection to the state database, committed on the way out.

    Per call rather than per process: a connection is cheap against a local file,
    and it keeps a long-lived daemon from sitting on a stale read snapshot while
    something else writes. busy_timeout is what replaces the old lock file --
    a writer waits for its turn instead of failing.
    """
    global _ready
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STATE_DB, timeout=5.0, isolation_level="DEFERRED")
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        if not _ready:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(_SCHEMA)
            _migrate_json(conn)
            conn.commit()
            _ready = True
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate_json(conn) -> None:
    """Import pins.json and frecency.json once, if they are still around.

    The old files are left exactly where they are: the previous generation of
    these scripts still reads them, and a one-way door here would strand anyone
    who switched back. The meta row is what stops a second import.
    """
    if conn.execute("SELECT 1 FROM meta WHERE key = 'json_imported'").fetchone():
        return
    conn.execute("INSERT INTO meta(key, value) VALUES('json_imported', ?)",
                 (time.strftime("%Y-%m-%d %H:%M:%S"),))

    def read(name):
        try:
            return json.loads((RONIN_CACHE_DIR / name).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    frecency = read("frecency.json")
    for path, e in (frecency.get("files") or {}).items():
        conn.execute(
            "INSERT OR REPLACE INTO files(path, visits, edits, last_ts, last_line, last_col)"
            " VALUES(?,?,?,?,?,?)",
            (path, e.get("visits", 0), e.get("edits", 0), e.get("last_ts", 0),
             e.get("last_line", 1), e.get("last_col", 0)))
    for key, e in (frecency.get("symbols") or {}).items():
        if "::" in key:  # the old composite key, now two columns
            file, symbol = key.rsplit("::", 1)
            conn.execute(
                "INSERT OR REPLACE INTO symbols(file, symbol, visits, last_ts, line)"
                " VALUES(?,?,?,?,?)",
                (file, symbol, e.get("visits", 0), e.get("last_ts", 0), e.get("line", 0)))
    for from_file, destinations in (frecency.get("co_visits") or {}).items():
        for to_file, count in destinations.items():
            conn.execute("INSERT OR REPLACE INTO co_visits(from_file, to_file, count)"
                         " VALUES(?,?,?)", (from_file, to_file, count))

    for slot, pin in enumerate(read("pins.json").get("pins") or [], start=1):
        if pin and pin.get("file") and slot <= NUM_PIN_SLOTS:
            conn.execute("INSERT OR REPLACE INTO pins(slot, file, line, col) VALUES(?,?,?,?)",
                         (slot, pin["file"], pin.get("line", 1), pin.get("col", 0)))


def _existing(rows, path_index: int):
    """Drop rows whose file is gone. Cheaper here than as a SQL function."""
    return [row for row in rows if Path(row[path_index]).exists()]


# ============================================================================
# Recording
# ============================================================================
def _record_file(path: str, line, col, field: str) -> None:
    """Bump a file's visit or edit counter and remember where the user was.

    `field` is one of two literals from the two callers below, never input.
    """
    with _db() as db:
        db.execute(
            f"INSERT INTO files(path, {field}, last_ts, last_line, last_col) VALUES(?,1,?,?,?)"
            f" ON CONFLICT(path) DO UPDATE SET {field} = {field} + 1,"
            f" last_ts = excluded.last_ts, last_line = excluded.last_line,"
            f" last_col = excluded.last_col",
            (path, time.time(), int(line), int(col)))


def record_visit(filepath: str, line=1, col=0) -> None:
    """Record that the user navigated to filepath at line/col."""
    _record_file(filepath, line, col, "visits")


def record_edit(filepath: str, line=1, col=0) -> None:
    """Record that the user saved filepath, and drag any pin on it along."""
    _record_file(filepath, line, col, "edits")
    update_pin_position(filepath, int(line), int(col))


def record_symbol_visit(symbol: str, file: str = "", line=0) -> None:
    """Record a visit to a symbol at a known location.

    file is required: a name alone is not enough for the sidebar to jump without
    re-running sakura, so location-less calls are dropped. A line of 0 means
    "wherever it was last seen", so it must not overwrite a known line.
    """
    if not symbol or not file:
        return
    with _db() as db:
        db.execute(
            "INSERT INTO symbols(file, symbol, visits, last_ts, line) VALUES(?,?,1,?,?)"
            " ON CONFLICT(file, symbol) DO UPDATE SET visits = visits + 1,"
            " last_ts = excluded.last_ts,"
            " line = CASE WHEN excluded.line > 0 THEN excluded.line ELSE line END",
            (file, symbol, time.time(), int(line)))


def record_co_visit(from_file: str, to_file: str) -> None:
    """Record a jump from one file to another, for co-visit ranking."""
    if not from_file or not to_file or from_file == to_file:
        return
    with _db() as db:
        db.execute("INSERT INTO co_visits(from_file, to_file, count) VALUES(?,?,1)"
                   " ON CONFLICT(from_file, to_file) DO UPDATE SET count = count + 1",
                   (from_file, to_file))


# ============================================================================
# Rankings
# ============================================================================
def sort_symbol_candidates(lines: list, current_file: str) -> list:
    """Order sakura candidate rows (file@line@col@symbol) by likely relevance.

    Current-file symbols first, then by symbol-visit frecency plus how often the
    user has navigated from current_file to the candidate's file. Symbol scores
    use visits only -- there is no such thing as editing a symbol.
    """
    if not lines:
        return lines
    with _db() as db:
        scores = {(f, s): score for f, s, score in db.execute(
            f"SELECT file, symbol, visits * {_DECAY} FROM symbols", {"now": time.time()})}
        co_visits = dict(db.execute(
            "SELECT to_file, count FROM co_visits WHERE from_file = ?", (current_file,))
        ) if current_file else {}

    def sort_key(line: str):
        fields = line.split("@")
        file = fields[0] if fields else ""
        symbol = fields[3] if len(fields) >= 4 else ""
        score = scores.get((file, symbol), 0.0) + co_visits.get(file, 0) * 0.5
        return (-(file == current_file), -score)

    return sorted(lines, key=sort_key)


def get_hot_symbols(limit: int) -> list[tuple[str, str, int]]:
    """Top-`limit` (symbol, file, line) by visit frecency, hottest first.

    Entries without a location or whose file is gone are skipped -- and skipped
    before the limit applies, so a deleted file cannot cost the sidebar a row.
    """
    with _db() as db:
        rows = db.execute(
            f"SELECT symbol, file, line FROM symbols"
            f" WHERE line > 0 AND last_ts > 0 AND visits > 0"
            f" ORDER BY visits * {_DECAY} DESC", {"now": time.time()}).fetchall()
    return [(s, f, l) for s, f, l in _existing(rows, 1)[:limit]]


def get_recent_files() -> list[tuple[float, str, int, int]]:
    """(ts, file, line, col) for every known file, most-recent first.

    The sidebar's Trail and jump_to_trail share this, so both agree on what the
    row labelled 5 means.
    """
    with _db() as db:
        rows = db.execute("SELECT last_ts, path, last_line, last_col FROM files"
                          " WHERE last_ts > 0 ORDER BY last_ts DESC").fetchall()
    return _existing(rows, 1)


def frecency_sorted_files() -> str:
    """Existing files as file@line@col rows, best-scoring first.

    Feeds the top of the file picker, so the files you keep coming back to are
    the ones already under the cursor. An edit counts for three visits.
    """
    with _db() as db:
        rows = db.execute(
            f"SELECT path, last_line, last_col FROM files"
            f" ORDER BY (visits + edits * 3) * {_DECAY} DESC", {"now": time.time()}).fetchall()
    return "\n".join(f"{p}@{line}@{col}" for p, line, col in _existing(rows, 0))


# ============================================================================
# Pins
# ============================================================================
def load_pins() -> list:
    """The pins array, always NUM_PIN_SLOTS long, empty slots as None."""
    pins = [None] * NUM_PIN_SLOTS
    with _db() as db:
        for slot, file, line, col in db.execute(
                "SELECT slot, file, line, col FROM pins WHERE slot BETWEEN 1 AND ?",
                (NUM_PIN_SLOTS,)):
            pins[slot - 1] = {"file": file, "line": line, "col": col}
    return pins


def set_pin(slot, file: str, line=1, col=0) -> None:
    """Point the 1-indexed slot at file:line:col.

    (file, line) is unique across slots: pinning foo.py:42 into slot 2 while slot
    1 already holds it clears slot 1, so the pin moves rather than duplicating.
    The same file at a *different* line is fine -- that is two bookmarks in one
    file.
    """
    slot, line, col = int(slot), int(line), int(col)
    if not (1 <= slot <= NUM_PIN_SLOTS) or not file:
        return
    with _db() as db:
        db.execute("DELETE FROM pins WHERE file = ? AND line = ? AND slot <> ?",
                   (file, line, slot))
        db.execute("INSERT OR REPLACE INTO pins(slot, file, line, col) VALUES(?,?,?,?)",
                   (slot, file, line, col))


def clear_pin(slot) -> None:
    with _db() as db:
        db.execute("DELETE FROM pins WHERE slot = ?", (int(slot),))


def update_pin_position(filepath: str, line: int, col: int) -> None:
    """Move the pin on filepath to line/col, if exactly one pin points there.

    Called on save. Two pins on one file are two distinct bookmarks at different
    lines; moving both would collapse them into one position, so that case is
    left alone and the user can re-pin explicitly. The WHERE clause skips the
    write when nothing moved, which keeps the sidebar from redrawing for nothing.
    """
    if not filepath:
        return
    with _db() as db:
        slots = db.execute("SELECT slot FROM pins WHERE file = ?", (filepath,)).fetchall()
        if len(slots) == 1:
            db.execute("UPDATE pins SET line = ?, col = ? WHERE slot = ?"
                       " AND (line <> ? OR col <> ?)",
                       (line, col, slots[0][0], line, col))
