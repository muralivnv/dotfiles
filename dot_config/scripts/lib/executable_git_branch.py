#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = ["pygit2"]
# ///

import datetime
import sys
from re import sub

import pygit2

C_CYAN        = "\033[36m"
C_ORANGE      = "\033[38;5;214m"
C_GREEN       = "\033[32m"
C_YELLOW      = "\033[33m"
C_BOLD_RED    = "\033[1;31m"
C_BOLD_PURPLE = "\033[1;35m"
C_RESET       = "\033[0m"

MAX_BRANCH_LEN = 50
DELIMITER      = "@"


def truncate(s: str) -> str:
    return s[:MAX_BRANCH_LEN - 1] + "…" if len(s) > MAX_BRANCH_LEN else s


def strip_ansi(s: str) -> str:
    return sub(r"\x1b\[[0-9;]*m", "", s)


def format_time(unix_ts: int) -> str:
    return datetime.datetime.fromtimestamp(unix_ts).strftime("%Y-%m-%d %H:%M")


def main():
    repo_path = pygit2.discover_repository(".")
    if not repo_path:
        return
    repo = pygit2.Repository(repo_path)

    try:
        current_branch = repo.head.shorthand
        head_is_detached = repo.head_is_detached
    except pygit2.GitError:
        current_branch = ""
        head_is_detached = True

    rows = []

    # --- Local branches ---
    tracked_upstreams = set()
    for name in repo.branches.local:
        branch = repo.branches.local[name]
        commit = branch.peel(pygit2.Commit)
        upstream = branch.upstream

        if upstream:
            upstream_name = upstream.shorthand
            tracked_upstreams.add(upstream_name)
            ahead, behind = repo.ahead_behind(branch.target, upstream.target)
        else:
            upstream_name = ">>> NO-REMOTE <<<"
            ahead, behind = 0, 0

        priority = 1
        display_branch = truncate(name)
        if not head_is_detached and name == current_branch:
            display_branch = f"{C_BOLD_RED}{display_branch}{C_RESET}"
            priority = 0

        rows.append([
            priority,
            commit.commit_time,
            name,
            f"{C_CYAN}{display_branch}{C_RESET}",
            f"{C_ORANGE}{truncate(upstream_name)}{C_RESET}",
            f"↑ {C_GREEN}{ahead}{C_RESET} ↓ {C_GREEN}{behind}{C_RESET}",
            f"{C_GREEN}{commit.author.name} {format_time(commit.commit_time)}{C_RESET}",
            f"{C_BOLD_PURPLE}{commit.message.split(chr(10), 1)[0]}{C_RESET}",
        ])

    # --- Remote-only branches (not tracked by any local branch) ---
    for name in repo.branches.remote:
        if name.endswith("/HEAD"):
            continue
        shorthand = name
        if shorthand in tracked_upstreams:
            continue
        branch = repo.branches.remote[name]
        commit = branch.peel(pygit2.Commit)
        rows.append([
            2,
            commit.commit_time,
            shorthand,
            f"{C_ORANGE}{truncate(shorthand)}{C_RESET}",
            "",
            "",
            f"{C_GREEN}{commit.author.name} {format_time(commit.commit_time)}{C_RESET}",
            f"{C_BOLD_PURPLE}{commit.message.split(chr(10), 1)[0]}{C_RESET}",
        ])

    rows.sort(key=lambda r: (r[0], -r[1]))

    # Build printable columns (drop priority + timestamp + full_name)
    full_names = [row[2] for row in rows]
    printable = [row[3:] for row in rows]

    if not printable:
        return

    col_widths = [max(len(strip_ansi(col)) for col in colset) for colset in zip(*printable)]

    for line_num, (full_name, row) in enumerate(zip(full_names, printable), start=1):
        aligned = []
        for col, width in zip(row, col_widths):
            aligned.append(col + " " * (width - len(strip_ansi(col))))
        print(f"{full_name}{DELIMITER}{line_num}{DELIMITER}{'  '.join(aligned)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
