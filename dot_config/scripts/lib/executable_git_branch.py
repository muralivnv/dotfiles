#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

import subprocess
import datetime
import sys
from re import sub

C_CYAN        = "\033[36m"
C_ORANGE      = "\033[38;5;214m"
C_GREEN       = "\033[32m"
C_YELLOW      = "\033[33m"
C_BOLD_RED    = "\033[1;31m"
C_BOLD_PURPLE = "\033[1;35m"
C_RESET       = "\033[0m"

def run_git(cmd):
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return result.stdout.strip()

def main():
    current_branch = run_git("git symbolic-ref --quiet --short HEAD")

    local_branches = run_git(
        "git for-each-ref --count=50 "
        "--format='%(refname)<|>%(refname:short)<|>%(upstream:short)<|>%(committerdate:unix)<|>%(objectname:short)<|>%(authorname)<|>%(contents:subject)' refs/heads"
    )

    remote_branches = run_git(
        "git for-each-ref --count=50 "
        "--format='%(refname)<|>%(refname:short)<|>%(committerdate:unix)<|>%(authorname)<|>%(contents:subject)' refs/remotes"
    )

    rows = []

    # Local branches
    for line in local_branches.splitlines():
        parts = line.strip("'").split("<|>")
        if len(parts) < 7:
            continue
        _, local_branch, upstream, unixdate, _, author, subject = parts

        if not upstream:
            upstream = ">>> NO-REMOTE <<<"
            ahead, behind = "0", "0"
        else:
            counts = run_git(f'git rev-list --left-right --count "{local_branch}...{upstream}"')
            ahead, behind = counts.split("\t") if counts else ("0", "0")

        priority = 1
        if local_branch == current_branch:
            local_branch = f"{C_BOLD_RED}{local_branch}{C_RESET}"
            priority = 0

        rows.append([
            priority,
            int(unixdate),
            "local",
            f"{C_CYAN}{local_branch}{C_RESET}",
            f"{C_ORANGE}{upstream}{C_RESET}",
            f"↑ {C_GREEN}{ahead}{C_RESET} ↓ {C_GREEN}{behind}{C_RESET}",
            f"{C_GREEN}{author} {datetime.datetime.fromtimestamp(int(unixdate)).strftime('%Y-%m-%d %H:%M')}{C_RESET}",
            f"{C_BOLD_PURPLE}{subject}{C_RESET}",
        ])

    # Remote branches
    tracked = set(run_git("git for-each-ref --format='%(upstream:short)' refs/heads").splitlines())
    for line in remote_branches.splitlines():
        parts = line.split("<|>")
        if len(parts) < 5:
            continue
        _, remote_branch, unixdate, author, subject = parts
        if remote_branch not in tracked:
            rows.append([
                2,
                int(unixdate),
                "remote",
                f"{C_ORANGE}{remote_branch}{C_RESET}",
                "",
                "",
                f"{C_GREEN}{author} {datetime.datetime.fromtimestamp(int(unixdate)).strftime('%Y-%m-%d %H:%M')}{C_RESET}",
                f"{C_BOLD_PURPLE}{subject}{C_RESET}",
            ])

    # Sort rows
    rows.sort(key=lambda r: (r[0], -r[1]))

    # Drop priority and date columns for printing
    printable = [row[3:] for row in rows]

    col_widths = [max(len(strip_ansi(col)) for col in colset) for colset in zip(*printable)]

    # Print with alignment
    for row in printable:
        out_parts = []
        for col, width in zip(row, col_widths):
            out_parts.append(col + " " * (width - len(strip_ansi(col))))
        print("  ".join(out_parts))

def strip_ansi(s):
    return sub(r"\x1b\[[0-9;]*m", "", s)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
