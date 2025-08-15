#!/usr/bin/env python3
from re import match
from subprocess import run, CalledProcessError
import sys
from readline import set_startup_hook, insert_text
from typing import Optional

def _extract_branch(text) -> Optional[str]:
    m = match(r"^\d+@([A-Za-z0-9._/-]+)\s+", text)
    if m:
        branch = m.group(1)
        if branch.startswith("origin/"):
            branch = branch[len("origin/") :]
        return branch
    return None

def _run_editable_command(initial_cmd) -> bool:
    set_startup_hook(lambda: insert_text(initial_cmd))
    try:
        user_cmd = input()
    finally:
        set_startup_hook(None)

    if not user_cmd.strip():
        return False
    try:
        run(user_cmd, shell=True, check=True)
        return True
    except CalledProcessError:
        print()
        try:
            input()
        except EOFError:
            pass
        return False

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
