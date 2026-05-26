"""Pin state: fixed-length array of user-curated jump slots in .ronin/pins.json.

Each slot is either null or {"file": str, "line": int, "col": int}. The file
is mirrored in the sidebar pane so slot N is always the same file — position
stability is what makes `space N` work from muscle memory, unlike frecency
where rankings shift.

Auto-update via update_pin_position() keeps a pin's line/col in sync with the
user's last-saved position in that file (Harpoon-style — you come back to
where you left off, not where you originally pinned).
"""

import contextlib
import fcntl
import json
import os
import tempfile
from pathlib import Path

from config import PINS_FILE, NUM_PIN_SLOTS

_PINS_LOCK_PATH = PINS_FILE.with_suffix(".lock")


@contextlib.contextmanager
def _pins_locked():
    _PINS_LOCK_PATH.parent.mkdir(exist_ok=True, parents=True)
    with open(_PINS_LOCK_PATH, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _empty_pins() -> list:
    return [None] * NUM_PIN_SLOTS


def _normalize(pins: list) -> list:
    pins = list(pins)[:NUM_PIN_SLOTS]
    while len(pins) < NUM_PIN_SLOTS:
        pins.append(None)
    return pins


def load_pins() -> list:
    """Return the pins array (length NUM_PIN_SLOTS), padding with None if short."""
    if not PINS_FILE.exists():
        return _empty_pins()
    try:
        with open(PINS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _normalize(data.get("pins", []))
    except (json.JSONDecodeError, OSError):
        return _empty_pins()


def _save_pins(pins: list) -> None:
    PINS_FILE.parent.mkdir(exist_ok=True, parents=True)
    fd, tmp = tempfile.mkstemp(dir=PINS_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "pins": pins}, f, indent=2)
        os.replace(tmp, PINS_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def set_pin(slot: int, file: str, line: int = 1, col: int = 0) -> None:
    """Assign the 1-indexed slot to the given file/line/col.

    Enforces (file, line) uniqueness across slots — pinning foo.py:42 into
    slot 2 when slot 1 already holds foo.py:42 clears slot 1 first, so the
    pin is effectively moved rather than duplicated. Same file at a *different*
    line is fine (user has two bookmarks in one file).
    """
    if not (1 <= slot <= NUM_PIN_SLOTS) or not file:
        return
    line, col = int(line), int(col)
    with _pins_locked():
        pins = load_pins()
        for i, p in enumerate(pins):
            if i == slot - 1:
                continue
            if p and p.get("file") == file and p.get("line") == line:
                pins[i] = None
        pins[slot - 1] = {"file": file, "line": line, "col": col}
        _save_pins(pins)


def clear_pin(slot: int) -> None:
    if not (1 <= slot <= NUM_PIN_SLOTS):
        return
    with _pins_locked():
        pins = load_pins()
        pins[slot - 1] = None
        _save_pins(pins)


def get_pin(slot: int) -> dict | None:
    if not (1 <= slot <= NUM_PIN_SLOTS):
        return None
    return load_pins()[slot - 1]


def update_pin_position(filepath: str, line: int, col: int) -> None:
    """If exactly ONE pin points at filepath, move its line/col to the given values.

    Called from record_edit so a pinned file's stored position tracks where the
    user left off. When *multiple* pins point at the same file, they're distinct
    bookmarks (different lines) — touching them would collapse them to a single
    position, so we skip instead. The user can re-pin explicitly if they want
    to change a specific bookmark.
    """
    if not filepath:
        return
    # Fast path: skip the lock entirely if no pin matches. Most saves are to
    # unpinned files; no point serialising those through the pins lock.
    initial = load_pins()
    if not any(p and p.get("file") == filepath for p in initial):
        return
    with _pins_locked():
        pins = load_pins()
        matching = [i for i, p in enumerate(pins) if p and p.get("file") == filepath]
        if len(matching) != 1:
            return
        idx = matching[0]
        p = pins[idx]
        if p.get("line") != line or p.get("col") != col:
            pins[idx] = {"file": filepath, "line": int(line), "col": int(col)}
            _save_pins(pins)
