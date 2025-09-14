#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

import subprocess

cS = "\033[1;32m"  # staged (green)
cU = "\033[1;31m"  # unstaged (red)
cQ = "\033[1;34m"  # untracked (blue)
c0 = "\033[0m"     # reset

def git_status_porcelain():
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    return result.stdout.splitlines()

def format_status_line(line):
    if line.startswith("??"):
        return f"{cQ}? {c0}{line[3:]}"
    staged = line[0]
    unstaged = line[1]
    filename = line[3:]

    output = []
    if staged != " ":
        output.append(f"{cS}S {c0}{filename}")
    if unstaged != " ":
        output.append(f"{cU}U {c0}{filename}")
    return "\n".join(output)

def main():
    for line in git_status_porcelain():
        formatted = format_status_line(line)
        if formatted:
            print(formatted)

if __name__ == "__main__":
    main()
