#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "prompt_toolkit"
# ]
# ///

from re import match
from subprocess import run, CalledProcessError
import sys
from typing import Optional
from prompt_toolkit import prompt

def _extract_branch(text) -> Optional[str]:
    m = match(r"^\d+@([A-Za-z0-9._/-]+)\s+", text)
    if m:
        branch = m.group(1)
        if branch.startswith("origin/"):
            branch = branch[len("origin/") :]
        return branch
    return None

def _run_editable_command(initial_cmd: str) -> None:
    try:
        user_cmd = prompt("💀 ", default=initial_cmd)
    except KeyboardInterrupt:
        return

    if not user_cmd.strip():
        return
    try:
        run(user_cmd, shell=True, check=True)
    except CalledProcessError as e:
        print("\nCommand failed.")
        print(e)
        try:
            input("Press Enter to continue...")
        except EOFError:
            pass

def checkout_branch(arg) -> None:
    branch = _extract_branch(arg)
    if branch:
        _run_editable_command(f'git switch "{branch}" ')

def reset_branch(arg):
    branch = _extract_branch(arg)
    if branch:
        _run_editable_command(f'git reset --hard "{branch}" ')

def delete_branch(arg):
    branch = _extract_branch(arg)
    if branch:
        _run_editable_command(f'git branch -d "{branch}" ')

def force_delete_branch(arg):
    branch = _extract_branch(arg)
    if branch:
        _run_editable_command(f'git branch -D "{branch}" ')

def create_branch(arg):
    branch = _extract_branch(arg)
    if branch:
        _run_editable_command(f'git branch >>>BRANCH-NAME<<< "{branch}"')

def pull_rebase():
    _run_editable_command("git pull --rebase ")

COMMANDS = {
    "checkout_branch"    : checkout_branch,
    "reset_branch"       : reset_branch,
    "delete_branch"      : delete_branch,
    "force_delete_branch": force_delete_branch,
    "create_branch"      : create_branch,
    "pull_rebase"        : pull_rebase,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: branch_actions.py <command> [args...]")
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    func = COMMANDS.get(cmd)
    if func:
        func(*args)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
