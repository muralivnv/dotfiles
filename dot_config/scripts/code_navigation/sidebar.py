#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = ["watchfiles"]
# ///

"""Live-updating sidebar for the code navigation system.

Runs inside its own tmux pane, alongside the Helix editor pane. Renders three
sections — Pins (curated slots 1-4), Trail (recent files 5-9), and Symbols
(hottest visited symbols, labels a-e). Re-renders whenever .ronin/*.json
changes (daemon updates) or SIGWINCH arrives (terminal resize).

The pane is display-only: stray keystrokes go to Python's unread stdin. Use
tmux to kill/close; toggle_sidebar() in commands.py manages the pane lifecycle.
"""

import json
import os
import shutil
import signal
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from watchfiles import watch, DefaultFilter

from config import (
    PINS_FILE, FRECENCY_FILE, NUM_PIN_SLOTS, NUM_TRAIL_ENTRIES, NUM_SYMBOL_ENTRIES,
)
from frecency import get_recent_files, get_hot_symbols

WATCH_DIR = Path(".ronin")
WATCH_ARGS = {
    "debounce": 150,
    "step": 50,
    "watch_filter": DefaultFilter(
        ignore_entity_patterns=(r"\.lock$", r"\.tmp$", r"\.pane$", r"\.sock$", r"\.pid$", r"\.log$"),
    ),
}

RELEVANT_FILES = {"pins.json", "frecency.json"}

RST = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
YEL = "\033[33m"
CYA = "\033[36m"
MAG = "\033[35m"

TRAIL_LABELS = "56789"       # matches Helix `space 5..9`
SYMBOL_LABELS = "ijklaeo"    # matches Helix `space i,j,k,l,a,e,o`

# Reserve space for ":NNNNN" in width budgets — forgetting this caused the
# trailing digits of a 4-digit line number to wrap onto the next row.
MAX_LINE_DIGITS = 5

_need_render = threading.Event()


def load_json(path: Path, default):
    try:
        if not path.exists():
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def load_pins_view() -> list:
    data = load_json(PINS_FILE, {"pins": []})
    pins = list(data.get("pins", []))[:NUM_PIN_SLOTS]
    while len(pins) < NUM_PIN_SLOTS:
        pins.append(None)
    return pins


def load_trail_and_current(pins: list) -> tuple[list, tuple[str, int, int] | None]:
    """Return (trail entries, current).

    The most-recently-touched file is "current"; the trail is the next
    NUM_TRAIL_ENTRIES, excluding any file that's already in Pins — otherwise
    the same file would occupy both a pin slot and a trail slot.
    """
    entries = get_recent_files()
    if not entries:
        return [], None
    _, cur_fp, cur_ln, cur_cl = entries[0]
    pinned_files = {p["file"] for p in pins if p}
    trail = [e for e in entries[1:] if e[1] not in pinned_files][:NUM_TRAIL_ENTRIES]
    return trail, (cur_fp, cur_ln, cur_cl)


def truncate(s: str, width: int) -> str:
    if len(s) <= width:
        return s
    if width <= 1:
        return s[:width]
    return s[: width - 1] + "…"


def divider(title: str, cols: int) -> str:
    head = f"── {title} "
    pad = max(0, cols - len(head))
    return f"{DIM}{head}{'─' * pad}{RST}"


def render_pins(pins: list, current_file: str, cols: int) -> list[str]:
    # Layout: " {marker}  {name}:{line}" → 5 fixed chars + name + line digits.
    name_width = max(4, cols - 5 - MAX_LINE_DIGITS)
    out = [divider("Pins", cols)]
    for i, pin in enumerate(pins, start=1):
        marker = f"{YEL}{i}{RST}"
        if pin:
            name = truncate(os.path.basename(pin["file"]), name_width)
            is_cur = pin["file"] == current_file
            styled = f"{BOLD}{name}{RST}" if is_cur else name
            out.append(f" {marker}  {styled}{DIM}:{pin.get('line', 1)}{RST}")
        else:
            out.append(f" {marker}  {DIM}—{RST}")
    return out


def render_trail(trail: list, cols: int) -> list[str]:
    # Same layout as Pins: " {marker}  {name}:{line}".
    name_width = max(4, cols - 5 - MAX_LINE_DIGITS)
    out = [divider("Trail", cols)]
    for i in range(NUM_TRAIL_ENTRIES):
        label_char = TRAIL_LABELS[i] if i < len(TRAIL_LABELS) else "·"
        if i < len(trail):
            _, fp, ln, _ = trail[i]
            marker = f"{CYA}{label_char}{RST}"
            name = truncate(os.path.basename(fp), name_width)
            out.append(f" {marker}  {name}{DIM}:{ln}{RST}")
        else:
            marker = f"{DIM}{label_char}{RST}"
            out.append(f" {marker}  {DIM}—{RST}")
    return out


def render_symbols(cols: int) -> list[str]:
    """Top-N hottest symbols, two-column layout: name on the left, file:line dim on the right.

    Width is split ~3/5 symbol name, ~2/5 filename — long symbol names truncate
    before stealing space from the file hint, which is usually the shorter of the two.
    """
    symbols = get_hot_symbols(NUM_SYMBOL_ENTRIES)
    out = [divider("Symbols", cols)]
    # Layout: " {marker}  {name:padded} {basename}:{line}" → 6 fixed chars + name + file + line digits.
    budget = max(10, cols - 6 - MAX_LINE_DIGITS)
    name_width = max(6, budget * 3 // 5)
    file_width = max(4, budget - name_width)
    for i in range(NUM_SYMBOL_ENTRIES):
        label_char = SYMBOL_LABELS[i] if i < len(SYMBOL_LABELS) else "·"
        if i < len(symbols):
            sym, fp, ln = symbols[i]
            marker = f"{MAG}{label_char}{RST}"
            name = truncate(sym, name_width)
            basename = truncate(os.path.basename(fp), file_width)
            pad = name_width - len(name)
            out.append(f" {marker}  {name}{' ' * pad} {DIM}{basename}:{ln}{RST}")
        else:
            marker = f"{DIM}{label_char}{RST}"
            out.append(f" {marker}  {DIM}—{RST}")
    return out


def render() -> None:
    cols, rows = shutil.get_terminal_size((40, 24))
    pins = load_pins_view()
    trail, current = load_trail_and_current(pins)

    current_file = current[0] if current else ""
    lines: list[str] = []
    lines.extend(render_pins(pins, current_file, cols))
    lines.append("")
    lines.extend(render_trail(trail, cols))
    lines.append("")
    lines.extend(render_symbols(cols))

    # Home + per-line clear + clear-to-end. Avoids the full-clear flash.
    buf = ["\033[H"]
    for i, line in enumerate(lines[:rows]):
        buf.append(line)
        buf.append("\033[0K")
        if i < rows - 1:
            buf.append("\r\n")
    buf.append("\033[0J")
    sys.stdout.write("".join(buf))
    sys.stdout.flush()


def file_watcher(stop_event: threading.Event) -> None:
    try:
        for changes in watch(str(WATCH_DIR), stop_event=stop_event, **WATCH_ARGS):
            if any(os.path.basename(path) in RELEVANT_FILES for _, path in changes):
                _need_render.set()
    except Exception:
        pass


def _on_winch(_signum, _frame) -> None:
    _need_render.set()


def _on_exit(_signum=None, _frame=None) -> None:
    sys.stdout.write("\033[?25h")  # show cursor
    sys.stdout.flush()
    sys.exit(0)


def main() -> None:
    WATCH_DIR.mkdir(exist_ok=True)

    signal.signal(signal.SIGWINCH, _on_winch)
    signal.signal(signal.SIGTERM, _on_exit)
    signal.signal(signal.SIGHUP, _on_exit)

    sys.stdout.write("\033[?25l\033[2J")  # hide cursor, clear screen
    sys.stdout.flush()

    stop_event = threading.Event()
    threading.Thread(target=file_watcher, args=(stop_event,), daemon=True).start()

    try:
        render()
        while True:
            _need_render.wait()
            _need_render.clear()
            render()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
