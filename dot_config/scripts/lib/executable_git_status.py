#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = ["pygit2"]
# ///

import pygit2

cS = "\033[1;32m"  # staged (green)
cU = "\033[1;31m"  # unstaged (red)
cQ = "\033[1;34m"  # untracked (blue)
cC = "\033[1;33m"  # conflicted (yellow)
c0 = "\033[0m"     # reset

DELIMITER = "@"

HIDE_PAD = " " * 300

INDEX_FLAGS = (
    pygit2.GIT_STATUS_INDEX_NEW
    | pygit2.GIT_STATUS_INDEX_MODIFIED
    | pygit2.GIT_STATUS_INDEX_DELETED
    | pygit2.GIT_STATUS_INDEX_RENAMED
    | pygit2.GIT_STATUS_INDEX_TYPECHANGE
)

WT_FLAGS = (
    pygit2.GIT_STATUS_WT_MODIFIED
    | pygit2.GIT_STATUS_WT_DELETED
    | pygit2.GIT_STATUS_WT_TYPECHANGE
    | pygit2.GIT_STATUS_WT_RENAMED
)


def main():
    repo_path = pygit2.discover_repository(".")
    if not repo_path:
        return
    repo = pygit2.Repository(repo_path)
    for path, flags in repo.status().items():
        if flags == pygit2.GIT_STATUS_IGNORED:
            continue

        if flags & pygit2.GIT_STATUS_CONFLICTED:
            print(f"{cC}C {c0}{path}{HIDE_PAD}\tC{DELIMITER}{path}")
        elif flags & pygit2.GIT_STATUS_WT_NEW:
            print(f"{cQ}? {c0}{path}{HIDE_PAD}\t?{DELIMITER}{path}")
        else:
            if flags & INDEX_FLAGS:
                print(f"{cS}S {c0}{path}{HIDE_PAD}\tS{DELIMITER}{path}")
            if flags & WT_FLAGS:
                print(f"{cU}U {c0}{path}{HIDE_PAD}\tU{DELIMITER}{path}")


if __name__ == "__main__":
    main()
