#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""CLI entry point for code navigation commands.

Delegates to picker/navigation functions in commands.py and frecency.py.
Can be run directly or via the navc daemon wrapper for zero startup latency.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from argparse import ArgumentParser
from commands import (
    open_file_picker, open_content_picker, open_symbol_picker,
    open_frecency_picker, open_last_picker,
    goto_definition, show_references,
    pin_current, clear_pin_slot, jump_to_pin, jump_to_trail,
    jump_to_symbol, toggle_sidebar,
)
from frecency import record_edit


def main():
    """Parse CLI arguments and dispatch to the appropriate navigation command."""
    parser = ArgumentParser(description="Code navigation")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("files")
    sub.add_parser("content")
    sub.add_parser("frecency")
    sub.add_parser("last")

    p = sub.add_parser("symbols")
    p.add_argument("--file", default="")
    p.add_argument("--current-file", default="")

    p = sub.add_parser("goto-def")
    p.add_argument("--symbol", required=True)
    p.add_argument("--current-file", default="")

    p = sub.add_parser("show-refs")
    p.add_argument("--symbol", required=True)
    p.add_argument("--current-file", default="")

    p = sub.add_parser("record-edit")
    p.add_argument("file")
    p.add_argument("--line", type=int, default=1)
    p.add_argument("--col", type=int, default=0)

    p = sub.add_parser("pin")
    p.add_argument("--slot", type=int, required=True)
    p.add_argument("--current-file", default="")
    p.add_argument("--line", type=int, default=1)
    p.add_argument("--col", type=int, default=0)

    p = sub.add_parser("clear-pin")
    p.add_argument("--slot", type=int, required=True)

    p = sub.add_parser("jump-pin")
    p.add_argument("--slot", type=int, required=True)

    p = sub.add_parser("jump-trail")
    p.add_argument("--index", type=int, required=True)

    p = sub.add_parser("jump-symbol")
    p.add_argument("--index", type=int, required=True)

    sub.add_parser("toggle-sidebar")

    args = parser.parse_args()

    match args.command:
        case "files":          open_file_picker()
        case "content":        open_content_picker()
        case "frecency":       open_frecency_picker()
        case "last":           open_last_picker()
        case "symbols":        open_symbol_picker(file=args.file, current_file=args.current_file)
        case "goto-def":       goto_definition(args.symbol, current_file=args.current_file)
        case "show-refs":      show_references(args.symbol, current_file=args.current_file)
        case "record-edit":    record_edit(args.file, args.line, args.col)
        case "pin":            pin_current(args.slot, args.current_file, args.line, args.col)
        case "clear-pin":      clear_pin_slot(args.slot)
        case "jump-pin":       jump_to_pin(args.slot)
        case "jump-trail":     jump_to_trail(args.index)
        case "jump-symbol":    jump_to_symbol(args.index)
        case "toggle-sidebar": toggle_sidebar()
        case _:                parser.print_help()


if __name__ == "__main__":
    main()
