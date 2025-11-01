#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///

import subprocess
import socket
import os

FZF_ESC_RET_CODE   = 130
SCRIPT_DIR         = os.path.dirname(os.path.abspath(__file__))
REPO_SCRIPT        = os.path.join(SCRIPT_DIR, "git_repo_list.py")
LOG_SCRIPT         = os.path.join(SCRIPT_DIR, "git_log.py")
STATUS_SCRIPT      = os.path.join(SCRIPT_DIR, "lib/git_status.py")
COMMIT_ACTIONS     = os.path.join(SCRIPT_DIR, "lib/commit_actions.py")
TMUX_POPUP         = r'tmux display-popup -w 60% -h 60% -d "$(git rev-parse --show-toplevel)" -DE '
TMUX_PANE          = r'tmux split-window -v -p 40 -c "$(git rev-parse --show-toplevel)" '
GIT_STATUS_COMMAND = f"uv run {STATUS_SCRIPT}"
PREFIX_EXTRACTION  = "$(echo {} | cut -c1) "
FILE_EXTRACTION    = "$(echo {} | cut -c3-) "

PREVIEW_COMMAND = (
    "--preview '"
    f"prefix={PREFIX_EXTRACTION}; "
    f"file={FILE_EXTRACTION}; "
    r'case "$prefix" in '
    r'S) git diff --cached -- "$file" | bat --language=Diff ;; '
    r'U) git diff -- "$file" | bat --language=Diff ;; '
    r'?) bat "$file" ;; '
    "esac'"
)

PATCH_COMMAND = (
    f"prefix={PREFIX_EXTRACTION}; "
    f"file={FILE_EXTRACTION}; "
    r'case "$prefix" in '
    r'S) git reset -p "$file" ;; '
    r'U) git add -p "$file" ;; '
    r'?) git add --intent-to-add "$file" && git add -p "$file" ;; '
    "esac"
)

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def is_git_repo() -> bool:
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False

class StatusPage:
    def __init__(self, port: int):
        self._base_command = (
            f"{GIT_STATUS_COMMAND} | fzf --listen {port} --ansi --preview-window=right:70% --reverse --cycle "
            f"{PREVIEW_COMMAND} --footer='Git Status' "
            f"--bind 'alt-s:execute-silent(git add {FILE_EXTRACTION})+reload-sync({GIT_STATUS_COMMAND})+down' "
            f"--bind 'alt-S:execute-silent(git add -u)+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-u:execute-silent(git restore --staged {FILE_EXTRACTION})+reload-sync({GIT_STATUS_COMMAND})+down' "
            f"--bind 'alt-U:execute-silent(git restore --staged .)+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-k:execute-silent(git restore {FILE_EXTRACTION})+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-K:execute-silent(rm -rf {FILE_EXTRACTION})+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-p:execute({PATCH_COMMAND})+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-g:reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-e:execute($EDITOR {FILE_EXTRACTION})' "
            f"--bind 'alt-c:execute-silent({TMUX_PANE} uv run {COMMIT_ACTIONS} commit_changes)' "
            f"--bind 'alt-P:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} push_changes)' "
            f"--bind 'alt-l:become(uv run {LOG_SCRIPT})' "
            f"--bind 'alt-t:execute-silent({TMUX_PANE})' "
             "--bind=tab:down,shift-tab:up "
            f"--bind 'alt-r:become(uv run {REPO_SCRIPT})' "
        )

    def run(self):
        try:
            subprocess.check_output(self._base_command, shell=True, universal_newlines=True)
            return True
        except subprocess.CalledProcessError as e:
            if e.returncode != FZF_ESC_RET_CODE:
                exit(e.returncode)
        return False

if __name__ == "__main__":
    if not is_git_repo():
        print("[ERROR] Not inside a Git repository.")
        exit(1)
    free_port = get_free_port()
    StatusPage(port=free_port).run()
