#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = ["pygit2"]
# ///

import subprocess
import socket
from pathlib import Path

import pygit2

FZF_ESC_RET_CODE   = 130
DELIMITER          = "@"
SCRIPT_DIR         = Path(__file__).resolve().parent
REPO_SCRIPT        = SCRIPT_DIR / "git_repo_list.py"
LOG_SCRIPT         = SCRIPT_DIR / "git_log.py"
STATUS_SCRIPT      = SCRIPT_DIR / "lib/git_status.py"
COMMIT_ACTIONS     = SCRIPT_DIR / "lib/commit_actions.py"
TMUX_POPUP         = r'tmux display-popup -w 60% -h 60% -d "$(git rev-parse --show-toplevel)" -E '
TMUX_PANE          = r'tmux split-window -v -p 40 -c "$(git rev-parse --show-toplevel)" '
GIT_STATUS_COMMAND = f"uv run {STATUS_SCRIPT}"

# {1} = prefix (S/U/?), {2} = filename (via --delimiter '@')
PREVIEW_COMMAND = (
    "--preview '"
    r'case {1} in '
    r'S) git diff --cached -- {2} | bat --language=Diff ;; '
    r'U) git diff -- {2} | bat --language=Diff ;; '
    r'"?") git diff --no-index /dev/null -- {2} | bat --language=Diff ;; '
    "esac'"
)

PATCH_COMMAND = (
    r'case {1} in '
    r'S) git reset -p -- {2} ;; '
    r'U) git add -p -- {2} ;; '
    r'"?") git add --intent-to-add -- {2} && git add -p -- {2} ;; '
    "esac"
)


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class StatusPage:
    def __init__(self, port: int):
        self._base_command = (
            f"{GIT_STATUS_COMMAND} | fzf --listen {port} --ansi --delimiter '{DELIMITER}' --with-nth=3.. "
            f"--preview-window=right:70% --reverse --cycle "
            f"{PREVIEW_COMMAND} --footer='Git Status' "
            f"--bind 'alt-s:execute-silent(git add -- {{2}})+reload-sync({GIT_STATUS_COMMAND})+down' "
            f"--bind 'alt-S:execute-silent(git add -u)+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-u:execute-silent(git restore --staged -- {{2}})+reload-sync({GIT_STATUS_COMMAND})+down' "
            f"--bind 'alt-U:execute-silent(git restore --staged .)+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-k:execute[f={{2}}; read -p \"Restore $f? [y/N] \" c && test \"$c\" = y && git restore -- \"$f\"]+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-K:execute[f={{2}}; read -p \"Delete $f? [y/N] \" c && test \"$c\" = y && rm -rf -- \"$f\"]+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-p:execute({PATCH_COMMAND})+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-g:reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-e:execute($EDITOR {{2}})' "
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
    if not pygit2.discover_repository("."):
        print("[ERROR] Not inside a Git repository.")
        exit(1)
    free_port = get_free_port()
    StatusPage(port=free_port).run()
