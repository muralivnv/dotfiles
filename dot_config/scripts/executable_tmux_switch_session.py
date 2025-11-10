#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///

import subprocess

SKIP_SESSIONS = {"yazi_session", "repl_session"}

def run(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()

if __name__ == "__main__":
    sessions = [line.split(':', 1)[0] for line in run("tmux list-sessions").splitlines()]
    if not sessions:
        exit(0)

    current = run("tmux display-message -p '#S'")
    if current not in sessions:
        exit(0)

    n = len(sessions)
    i = sessions.index(current)

    k = (i + 1) % n
    while k != i:
        candidate = sessions[k]
        if candidate not in SKIP_SESSIONS:
            subprocess.run(["tmux", "switch-client", "-t", candidate])
            exit(0)
        k = (k + 1) % n
