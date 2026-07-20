#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///

"""Navigation daemon — stays running to handle commands with zero startup cost.

Started automatically by navc on first use. Shuts down after 30 min idle.
Socket: nav.sock (per-project, located in RONIN_CACHE_DIR)

Protocol: line-delimited JSON.
  Request:  {"tmux":"...","pane":"...","cmd":"...","args":["--flag","val",...]}\n
  Response: {"ok":true}\n  |  {"ok":false}\n
"""

import json
import os
import sys
import socket
import signal
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import RONIN_CACHE_DIR, SOCK_PATH, PID_PATH, LOG_PATH

IDLE_TIMEOUT = 3600  # seconds


def log(msg):
    """Append a timestamped message to the daemon log file, silently ignoring I/O errors."""
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass


def main():
    """Start the navigation daemon: bind the Unix socket and serve commands until idle timeout."""
    RONIN_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Handle stale socket/pid
    if os.path.exists(SOCK_PATH):
        if os.path.exists(PID_PATH):
            try:
                pid = int(Path(PID_PATH).read_text().strip())
                os.kill(pid, 0)
                sys.exit(1)  # Another daemon is running
            except (ProcessLookupError, ValueError, FileNotFoundError):
                pass
        try:
            os.unlink(SOCK_PATH)
        except FileNotFoundError:
            pass

    Path(PID_PATH).write_text(str(os.getpid()))

    from commands import (
        open_file_picker, open_content_picker, open_symbol_picker,
        open_frecency_picker, open_last_picker,
        goto_definition, show_references,
        pin_current, clear_pin_slot, jump_to_pin, jump_to_trail,
        jump_to_symbol, toggle_sidebar,
    )
    from frecency import record_edit

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCK_PATH)) # socket bind often expects a string representation
    server.listen(8)
    server.settimeout(1.0)

    log(f"socket created at {str(SOCK_PATH)}")

    last_activity = time.monotonic()
    running = True

    def shutdown(signum=None, frame=None):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    def parse_kw(args, *keys):
        """Parse --key value pairs from an args list."""
        result = {}
        i = 0
        while i < len(args):
            matched = False
            for key in keys:
                if args[i] == f"--{key}" and i + 1 < len(args):
                    result[key.replace("-", "_")] = args[i + 1]
                    i += 2
                    matched = True
                    break
            if not matched:
                i += 1
        return result

    def handle(conn):
        """Read one JSON command from conn and dispatch it to the appropriate picker."""
        nonlocal last_activity
        ok = True
        try:
            data = b""
            conn.settimeout(2.0)
            try:
                while b"\n" not in data:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            except socket.timeout:
                pass

            line = data.decode().strip()
            if not line:
                return

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                ok = False
                log(f"bad request (invalid JSON): {line[:120]}")
                return

            last_activity = time.monotonic()
            tmux_val = msg.get("tmux", "")
            pane_val = msg.get("pane", "")
            cmd = msg.get("cmd", "")
            args = msg.get("args", [])

            # Set tmux context for this command
            if tmux_val:
                os.environ["TMUX"] = tmux_val
            if pane_val:
                os.environ["NAV_TMUX_PANE"] = pane_val

            if cmd == "files":
                open_file_picker(*args)
            elif cmd == "content":
                open_content_picker(*args)
            elif cmd == "frecency":
                open_frecency_picker(*args)
            elif cmd == "last":
                open_last_picker()
            elif cmd == "symbols":
                kw = parse_kw(args, "file", "current-file")
                open_symbol_picker(**kw)
            elif cmd == "goto-def":
                kw = parse_kw(args, "symbol", "current-file")
                if "symbol" in kw:
                    goto_definition(kw["symbol"], current_file=kw.get("current_file", ""))
            elif cmd == "show-refs":
                kw = parse_kw(args, "symbol", "current-file")
                if "symbol" in kw:
                    show_references(kw["symbol"], current_file=kw.get("current_file", ""))
            elif cmd == "record-edit":
                if args:
                    kw = parse_kw(args[1:], "line", "col")
                    record_edit(args[0], int(kw.get("line", 1)), int(kw.get("col", 0)))
            elif cmd == "pin":
                kw = parse_kw(args, "slot", "current-file", "line", "col")
                if "slot" in kw:
                    pin_current(int(kw["slot"]), kw.get("current_file", ""),
                                int(kw.get("line", 1)), int(kw.get("col", 0)))
            elif cmd == "clear-pin":
                kw = parse_kw(args, "slot")
                if "slot" in kw:
                    clear_pin_slot(int(kw["slot"]))
            elif cmd == "jump-pin":
                kw = parse_kw(args, "slot")
                if "slot" in kw:
                    jump_to_pin(int(kw["slot"]))
            elif cmd == "jump-trail":
                kw = parse_kw(args, "index")
                if "index" in kw:
                    jump_to_trail(int(kw["index"]))
            elif cmd == "jump-symbol":
                kw = parse_kw(args, "index")
                if "index" in kw:
                    jump_to_symbol(int(kw["index"]))
            elif cmd == "toggle-sidebar":
                toggle_sidebar()
            elif cmd == "stop":
                shutdown()

        except Exception:
            ok = False
            log(traceback.format_exc())
        finally:
            try:
                conn.send(b'{"ok":true}\n' if ok else b'{"ok":false}\n')
            except (BrokenPipeError, ConnectionResetError):
                pass
            conn.close()

    log("started")
    try:
        while running:
            try:
                conn, _ = server.accept()
                handle(conn)
            except socket.timeout:
                if time.monotonic() - last_activity > IDLE_TIMEOUT:
                    log("idle timeout")
                    break
    finally:
        server.close()
        for p in (SOCK_PATH, PID_PATH):
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass
        log("stopped")


if __name__ == "__main__":
    main()
