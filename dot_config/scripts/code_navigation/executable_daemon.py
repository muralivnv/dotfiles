#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///

"""Navigation daemon: stays running so a keypress costs no interpreter start.

Started by navc on first use, gone again after an hour idle. One Unix socket per
project, under RONIN_CACHE_DIR.

Protocol: one tab-delimited line per command, acknowledged with ok or err.
  TMUX \t PANE \t CMD \t ARG...
Everything after CMD is handed to commands.dispatch untouched, so the vocabulary
lives in one place -- commands.HANDLERS -- and this file never learns the names.

The acknowledgement is sent on *receipt*, not on completion: a picker runs until
the user picks, and a client that waited for that would hold a shell and a socat
open for the whole session. So ok means "this daemon has your command", and how it
went is in the log -- which is the other half of the deal, and why every command
is logged with the time it took.
"""

import contextlib
import os
import signal
import socket
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import LOG_PATH, PID_PATH, RONIN_CACHE_DIR, SOCK_PATH

IDLE_TIMEOUT = 3600      # seconds before an unused daemon gives the socket back
LOG_MAX_BYTES = 262144   # one generation kept; enough to explain what just broke


def log(msg) -> None:
    """Append a timestamped line to the daemon log, ignoring I/O failures.

    Rotated by size because this logs every command: a daemon left running for
    weeks should not be able to fill a disk.
    """
    with contextlib.suppress(OSError):
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > LOG_MAX_BYTES:
            LOG_PATH.replace(LOG_PATH.with_suffix(".log.1"))
        with open(LOG_PATH, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def claim_socket() -> bool:
    """Clear a stale socket, or report that a live daemon already owns it."""
    if not os.path.exists(SOCK_PATH):
        return True
    if os.path.exists(PID_PATH):
        with contextlib.suppress(ProcessLookupError, ValueError, FileNotFoundError):
            os.kill(int(Path(PID_PATH).read_text().strip()), 0)
            return False  # someone is home
    with contextlib.suppress(FileNotFoundError):
        os.unlink(SOCK_PATH)
    return True


def main() -> None:
    RONIN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not claim_socket():
        sys.exit(1)
    Path(PID_PATH).write_text(str(os.getpid()))

    # Imported after the socket is ours: no point paying for the command module
    # only to exit because another daemon is already serving this project.
    from commands import dispatch

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCK_PATH))  # bind wants a string, not a Path
    server.listen(8)
    server.settimeout(1.0)
    log(f"socket created at {SOCK_PATH}")

    state = {"last_activity": time.monotonic(), "running": True}

    def shutdown(_signum=None, _frame=None) -> None:
        state["running"] = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    def read_command(conn) -> str:
        """One line from conn, or empty if the client sent nothing in time."""
        conn.settimeout(2.0)
        data = b""
        with contextlib.suppress(socket.timeout):
            while b"\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
        return data.decode(errors="replace").strip("\n")

    def handle(conn) -> None:
        """Acknowledge one command, then run it."""
        try:
            line = read_command(conn)
            fields = line.split("\t") if line else []
            tmux, pane, cmd = (fields + ["", "", ""])[:3]
            args = fields[3:]

            with contextlib.suppress(OSError):
                conn.send(b"ok\n" if cmd else b"err\n")
        finally:
            conn.close()

        if not cmd:
            log(f"ignored malformed request: {line[:120]!r}")
            return

        state["last_activity"] = time.monotonic()

        # The editor's pane rides along with every command: the daemon outlives
        # any single one, so it cannot cache where to send :open.
        if tmux:
            os.environ["TMUX"] = tmux
        if pane:
            os.environ["NAV_TMUX_PANE"] = pane

        if cmd == "stop":
            log("stop requested")
            shutdown()
            return

        started = time.monotonic()
        try:
            dispatch(cmd, args)
            log(f"{cmd} {' '.join(args)} -> {(time.monotonic() - started) * 1000:.0f}ms")
        except Exception:
            log(f"{cmd} {' '.join(args)} -> failed\n{traceback.format_exc()}")

    log("started")
    try:
        while state["running"]:
            try:
                conn, _ = server.accept()
                handle(conn)
            except socket.timeout:
                if time.monotonic() - state["last_activity"] > IDLE_TIMEOUT:
                    log("idle timeout")
                    break
    finally:
        server.close()
        for path in (SOCK_PATH, PID_PATH):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)
        log("stopped")


if __name__ == "__main__":
    main()
