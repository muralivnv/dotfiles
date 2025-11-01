#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = [
#   "prompt_toolkit"
# ]
# ///

from os import environ, remove
from re import search
from subprocess import run, CalledProcessError
import sys
import tempfile
from typing import Optional
from prompt_toolkit import prompt

def extract_commit_hash(text) -> Optional[str]:
    m = search(r"\*\s+([a-z0-9]{4,})", text)
    if m:
        return m.group(1)
    return None

def _run_editable_command(initial_cmd: str) -> None:
    try:
        user_cmd = prompt("💀 ", default=initial_cmd)
    except KeyboardInterrupt:
        return

    if not user_cmd.strip():
        return
    try:
        run(f"{user_cmd} | less -XR", shell=True, check=True)
    except CalledProcessError as e:
        print("\nCommand failed.")
        print(e)
        try:
            input("Press Enter to continue...")
        except EOFError:
            pass

def checkout_commit(arg):
    commit = extract_commit_hash(arg)
    _run_editable_command(f'git checkout "{commit}" ')

def soft_reset_to_commit(arg):
    commit = extract_commit_hash(arg)
    _run_editable_command(f'git reset --soft "{commit}" ')

def hard_reset_to_commit(arg):
    commit = extract_commit_hash(arg)
    _run_editable_command(f'git reset --hard "{commit}" ')

def cherry_pick(arg):
    commit = extract_commit_hash(arg)
    _run_editable_command(f'git cherry-pick "{commit}" ')

def cherry_pick_no_commit(arg):
    commit = extract_commit_hash(arg)
    _run_editable_command(f'git cherry-pick --no-commit "{commit}" ')

def commit_changes():
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".diff", delete=False) as tmpfile:
        tmpfile_path = tmpfile.name
        msgfile_path = tmpfile_path + ".msg"

        tmpfile.write(">>> COMMIT_MESSAGE\n\n<<< COMMIT_MESSAGE\n<<<DIFF>>>\n")
        tmpfile.flush()
        run("git diff --staged", shell=True, check=False, stdout=tmpfile)

    editor = environ.get("EDITOR", "nano")
    run(f'{editor} "{tmpfile_path}"', shell=True)

    lines = []
    has_content = False
    with open(tmpfile_path, "r", encoding="utf8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.endswith("COMMIT_MESSAGE"):
                continue
            elif stripped == "<<<DIFF>>>":
                break
            lines.append(line)
            has_content |= bool(stripped)
    if lines and has_content:
        with open(msgfile_path, "w", encoding="utf8") as f:
            f.writelines(lines)
        run(f'git commit -F "{msgfile_path}"', shell=True)
        remove(tmpfile_path)
        remove(msgfile_path)
    else:
        print("Empty commit message -- aborting")

def push_changes():
    _run_editable_command("git push ")

COMMANDS = {
    "checkout_commit"      : checkout_commit,
    "soft_reset_to_commit" : soft_reset_to_commit,
    "hard_reset_to_commit" : hard_reset_to_commit,
    "cherry_pick"          : cherry_pick,
    "cherry_pick_no_commit": cherry_pick_no_commit,
    "commit_changes"       : commit_changes,
    "push_changes"         : push_changes,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: commit_actions.py <command> [args...]")
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    func = COMMANDS.get(cmd)
    if func:
        func(*args)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
