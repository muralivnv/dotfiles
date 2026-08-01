#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = ["watchfiles"]
# ///

import os
import shutil
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from watchfiles import watch

from config import (
    NUM_SYMBOL_ENTRIES, NUM_TRAIL_ENTRIES, PIN_LABELS, RONIN_CACHE_DIR,
    SYMBOL_LABELS, TRAIL_LABELS,
)
from state import get_hot_symbols, get_recent_files, load_pins

# Every commit in WAL mode touches state.db-wal, and only the checkpoints touch
# state.db, so the -wal file is the one that reliably says "something changed".
STATE_FILES = {"state.db", "state.db-wal"}

# yield_on_timeout turns the watcher into the whole event loop: a change yields a
# set of paths, a quiet second yields an empty one, and either way we look at the
# terminal size again. That is what a resize needs, so there is no signal handler
# and no second thread to coordinate with.
WATCH_ARGS = {"debounce": 150, "step": 50, "rust_timeout": 1000, "yield_on_timeout": True}

RST = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
YEL = "\033[33m"
CYA = "\033[36m"
MAG = "\033[35m"

# Reserve room for ":NNNNN" in the width budgets -- forgetting this wrapped the
# trailing digits of a four-digit line number onto the next row.
MAX_LINE_DIGITS = 5


def truncate(s: str, width: int) -> str:
    if len(s) <= width:
        return s
    return s[: width - 1] + "…" if width > 1 else s[:width]


def render_section(title: str, labels: str, entries: list, cols: int, colour: str) -> list[str]:
    """A divider, then one row per label: " <label>  <text><dim detail>".

    `entries` is (text, detail) pairs positionally aligned with `labels`, None
    where there is nothing to show -- holes matter, because a label's position is
    the whole point of it.
    """
    head = f"── {title} "
    out = [f"{DIM}{head}{'─' * max(0, cols - len(head))}{RST}"]
    for label, entry in zip(labels, entries):
        if entry is None:
            out.append(f" {DIM}{label}{RST}  {DIM}—{RST}")
        else:
            text, detail = entry
            out.append(f" {colour}{label}{RST}  {text}{DIM}{detail}{RST}")
    return out


def pad(entries: list, count: int) -> list:
    """Exactly `count` entries, padding the tail with None."""
    return (entries + [None] * count)[:count]


def name_and_line(path: str, line, width: int) -> tuple[str, str]:
    """Layout shared by Pins and Trail: " L  name:line" -> 5 fixed chars."""
    return truncate(os.path.basename(path), width), f":{line}"


def pin_entries(pins: list, current_file: str, cols: int) -> list:
    width = max(4, cols - 5 - MAX_LINE_DIGITS)
    entries = []
    for pin in pins:
        if not pin:
            entries.append(None)
            continue
        name, line = name_and_line(pin["file"], pin.get("line", 1), width)
        entries.append((f"{BOLD}{name}{RST}" if pin["file"] == current_file else name, line))
    return entries


def trail_entries(trail: list, cols: int) -> list:
    width = max(4, cols - 5 - MAX_LINE_DIGITS)
    return [name_and_line(fp, ln, width) for _, fp, ln, _ in trail]


def symbol_entries(cols: int) -> list:
    """Two columns: symbol on the left, dim basename:line on the right.

    Width splits ~3/5 to the symbol, so a long symbol truncates before it starts
    stealing space from the file hint.
    """
    budget = max(10, cols - 6 - MAX_LINE_DIGITS)
    name_width = max(6, budget * 3 // 5)
    file_width = max(4, budget - name_width)
    entries = []
    for symbol, path, line in get_hot_symbols(NUM_SYMBOL_ENTRIES):
        name = truncate(symbol, name_width)
        entries.append((f"{name}{' ' * (name_width - len(name))} ",
                        f"{truncate(os.path.basename(path), file_width)}:{line}"))
    return entries


def trail_and_current(pins: list) -> tuple[list, str]:
    """The trail rows and the current file.

    The most recently touched file is "current" and heads nothing; the trail is
    what follows, minus anything already pinned -- one file should not occupy a
    pin slot and a trail slot at once. jump_to_trail filters identically.
    """
    entries = get_recent_files()
    if not entries:
        return [], ""
    pinned = {p["file"] for p in pins if p}
    return [e for e in entries[1:] if e[1] not in pinned][:NUM_TRAIL_ENTRIES], entries[0][1]


def render() -> None:
    cols, rows = shutil.get_terminal_size((40, 24))
    pins = load_pins()
    trail, current_file = trail_and_current(pins)

    lines = [
        *render_section("Pins", PIN_LABELS, pin_entries(pins, current_file, cols), cols, YEL),
        "",
        *render_section("Trail", TRAIL_LABELS, pad(trail_entries(trail, cols), NUM_TRAIL_ENTRIES),
                        cols, CYA),
        "",
        *render_section("Symbols", SYMBOL_LABELS, pad(symbol_entries(cols), NUM_SYMBOL_ENTRIES),
                        cols, MAG),
    ]

    # Home, then clear each line as it is written and the rest at the end. A full
    # clear first would flash.
    buf = ["\033[H"]
    for i, line in enumerate(lines[:rows]):
        buf += [line, "\033[0K"]
        if i < rows - 1:
            buf.append("\r\n")
    buf.append("\033[0J")
    sys.stdout.write("".join(buf))
    sys.stdout.flush()


def _show_cursor_and_exit(_signum=None, _frame=None) -> None:
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()
    sys.exit(0)


def main() -> None:
    RONIN_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    signal.signal(signal.SIGTERM, _show_cursor_and_exit)
    signal.signal(signal.SIGHUP, _show_cursor_and_exit)

    sys.stdout.write("\033[?25l\033[2J")  # hide cursor, clear
    sys.stdout.flush()

    try:
        size = shutil.get_terminal_size()
        render()
        for changes in watch(str(RONIN_CACHE_DIR), **WATCH_ARGS):
            # The timeout tick carries no changes; it is there so a resize is
            # noticed. Redrawing on every tick regardless would keep a pane that
            # nothing is happening in busy once a second, for the same picture.
            size, resized = (new := shutil.get_terminal_size()), new != size
            if resized or any(os.path.basename(p) in STATE_FILES for _, p in changes):
                render()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
