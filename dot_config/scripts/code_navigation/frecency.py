import contextlib
import fcntl
import json
import os
import tempfile
import time
from pathlib import Path
from config import FRECENCY_FILE

_FRECENCY_LOCK_PATH = FRECENCY_FILE.with_suffix(".lock")


@contextlib.contextmanager
def _frecency_locked():
    """Acquire an exclusive advisory lock covering the frecency read-modify-write cycle.

    Uses a dedicated lock file so the frecency JSON is never held open during writes.
    Multiple processes (e.g. two terminals running nav.py directly) will serialise here.
    """
    _FRECENCY_LOCK_PATH.parent.mkdir(exist_ok=True, parents=True)
    with open(_FRECENCY_LOCK_PATH, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _load_frecency() -> dict:
    """Load frecency data from disk, returning a default empty structure on any error."""
    if not FRECENCY_FILE.exists():
        return {"version": 1, "files": {}}
    try:
        with open(FRECENCY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data.get("files"), dict):
            return {"version": 1, "files": {}}
        return data
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "files": {}}


def _save_frecency(data: dict) -> None:
    """Write frecency data atomically via a temp file and os.replace.

    Readers always see either the previous complete file or the new complete file —
    never a partial write. Must be called while _frecency_locked() is held.
    """
    FRECENCY_FILE.parent.mkdir(exist_ok=True, parents=True)
    fd, tmp = tempfile.mkstemp(dir=FRECENCY_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, FRECENCY_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _decay(hours: float) -> float:
    """Return the recency decay factor for an age given in hours.

    Steps: < 1h → 1.0,  < 6h → 0.8,  < 24h → 0.6,  < 7d → 0.4,  < 30d → 0.2,  else → 0.1
    """
    if hours < 1:   return 1.0
    if hours < 6:   return 0.8
    if hours < 24:  return 0.6
    if hours < 168: return 0.4
    if hours < 720: return 0.2
    return 0.1


def _frecency_score(entry: dict, now: float) -> float:
    """Compute a frecency score for a file entry based on visit/edit count and recency.

    Edits are weighted 3× more than visits.
    """
    hours = (now - entry.get("last_ts", 0)) / 3600.0
    return (entry.get("visits", 0) + entry.get("edits", 0) * 3) * _decay(hours)


def _record_file_activity(filepath: str, line: int, col: int, *, field: str) -> None:
    """Increment a visit or edit counter for a file and update its last-accessed position."""
    with _frecency_locked():
        data = _load_frecency()
        entry = data["files"].setdefault(filepath, {"visits": 0, "edits": 0, "last_ts": 0, "last_line": 1, "last_col": 0})
        entry[field] += 1
        entry["last_ts"] = time.time()
        entry["last_line"] = line
        entry["last_col"] = col
        _save_frecency(data)


def record_visit(filepath: str, line: int = 1, col: int = 0) -> None:
    """Increment the visit count for a file and update its last-accessed position."""
    _record_file_activity(filepath, line, col, field="visits")


def record_edit(filepath: str, line: int = 1, col: int = 0) -> None:
    """Increment the edit count for a file and update its last-accessed position."""
    _record_file_activity(filepath, line, col, field="edits")
    # Lazy import to avoid circular dep: pins.py → config.py, frecency.py → config.py.
    from pins import update_pin_position
    update_pin_position(filepath, line, col)


def _sym_key(file: str, symbol: str) -> str:
    """Storage key for a symbol, scoped to a specific file.

    Same-named symbols across files (many `handle`s, many `__init__`s) are
    genuinely different jump targets, so we key on (file, symbol). Without
    this, visits to one `handle` would be credited to every sibling and the
    sidebar couldn't jump without a disambiguation picker.

    Callers that need to reverse the key use rsplit("::", 1), so file paths
    containing `::` stay intact on the left.
    """
    return f"{file}::{symbol}"


def record_symbol_visit(symbol: str, file: str = "", line: int = 0) -> None:
    """Increment the visit count for a symbol at a specific location.

    Requires file+line so the sidebar can jump directly without re-running sakura.
    Calls without location are ignored — a symbol name alone isn't enough to jump.
    """
    if not symbol or not file:
        return
    with _frecency_locked():
        data = _load_frecency()
        symbols = data.setdefault("symbols", {})
        key = _sym_key(file, symbol)
        entry = symbols.setdefault(key, {"visits": 0, "last_ts": 0, "line": 0})
        entry["visits"] += 1
        entry["last_ts"] = time.time()
        if line:
            entry["line"] = line
        _save_frecency(data)


def record_co_visit(from_file: str, to_file: str) -> None:
    """Record a navigation from from_file to to_file for co-visit ranking."""
    if not from_file or not to_file or from_file == to_file:
        return
    with _frecency_locked():
        data = _load_frecency()
        co_visits = data.setdefault("co_visits", {})
        destinations = co_visits.setdefault(from_file, {})
        destinations[to_file] = destinations.get(to_file, 0) + 1
        _save_frecency(data)


def _sort_symbol_candidates(lines: list, current_file: str) -> list:
    """Sort symbol candidate lines by frecency, prioritising the current file.

    Scoring: current-file symbols sort first, then by combined symbol-visit frecency
    and co-visit score (how often to_file is navigated to from current_file).
    Symbol score uses visit count only (no edits multiplier, unlike file frecency).
    """
    if not lines:
        return lines
    data = _load_frecency()
    now = time.time()
    sym_data = data.get("symbols", {})
    co_visits = data.get("co_visits", {}).get(current_file, {}) if current_file else {}

    def sort_key(line: str):
        parts = line.split("@")
        file_path = parts[0] if parts else ""
        symbol = parts[3] if len(parts) >= 4 else ""
        is_current = file_path == current_file
        sym_entry = sym_data.get(_sym_key(file_path, symbol), {})
        sym_score = 0.0
        if sym_entry:
            hours = (now - sym_entry.get("last_ts", 0)) / 3600.0
            sym_score = sym_entry.get("visits", 0) * _decay(hours)
        co_score = co_visits.get(file_path, 0)
        return (-is_current, -(sym_score + co_score * 0.5))

    return sorted(lines, key=sort_key)


def get_hot_symbols(limit: int) -> list[tuple[str, str, int]]:
    """Return top-`limit` (symbol, file, line) by frecency, most-hot first.

    Skips entries missing location data (old-schema leftovers) and entries whose
    file no longer exists on disk. The sidebar and jump_to_symbol share this
    helper so they stay in sync — a label in the sidebar always points to the
    same symbol the jump command will resolve.
    """
    data = _load_frecency()
    now = time.time()
    scored = []
    for key, entry in data.get("symbols", {}).items():
        if "::" not in key:
            continue
        file_path, symbol = key.rsplit("::", 1)
        line = entry.get("line", 0)
        if not line:
            continue
        if not Path(file_path).exists():
            continue
        ts = entry.get("last_ts", 0)
        if not ts:
            continue
        visits = entry.get("visits", 0)
        if not visits:
            continue
        score = visits * _decay((now - ts) / 3600.0)
        if score <= 0:
            continue
        scored.append((score, symbol, file_path, line))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [(s, f, l) for _, s, f, l in scored[:limit]]


def get_recent_files(exclude: set[str] | None = None) -> list[tuple[float, str, int, int]]:
    """Return (ts, filepath, last_line, last_col) for known files, sorted most-recent-first.

    Skips files missing from disk, files with no recorded timestamp, and any filepath
    in `exclude`. Used by the sidebar trail and by jump_to_trail so both agree on the
    displayed list (including which entries to hide because they're already pinned).
    """
    exclude = exclude or set()
    data = _load_frecency()
    entries = []
    for fp, e in data.get("files", {}).items():
        if fp in exclude:
            continue
        if not Path(fp).exists():
            continue
        ts = e.get("last_ts", 0)
        if not ts:
            continue
        entries.append((ts, fp, e.get("last_line", 1), e.get("last_col", 0)))
    entries.sort(key=lambda x: x[0], reverse=True)
    return entries


def _get_frecency_sorted_file_list() -> str:
    """Return a newline-separated list of existing files sorted by frecency score.

    Each line is formatted as filepath@last_line@last_col, suitable for piping
    into fzf via the file picker.
    """
    data = _load_frecency()
    now = time.time()
    scored = {}
    for filepath, entry in data.get("files", {}).items():
        if Path(filepath).exists():
            scored[filepath] = (_frecency_score(entry, now), entry.get("last_line", 1), entry.get("last_col", 0))
    frecency_files = sorted(scored.keys(), key=lambda f: scored[f][0], reverse=True)
    return "\n".join(f"{f}@{scored[f][1]}@{scored[f][2]}" for f in frecency_files)
