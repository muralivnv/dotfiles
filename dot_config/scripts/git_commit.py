import subprocess
import os

FZF_ESC_RET_CODE = 130
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_SCRIPT = os.path.join(SCRIPT_DIR, "git_repo_list.py")
LOG_SCRIPT = os.path.join(SCRIPT_DIR, "git_log.py")
STATUS_PARSER_AWK_SCRIPT = os.path.join(SCRIPT_DIR, "lib/git_status_enhanced.awk")
COMMIT_ACTIONS = os.path.join(SCRIPT_DIR, "lib/commit_actions.sh")

GIT_STATUS_COMMAND = f"git status --porcelain | awk -f {STATUS_PARSER_AWK_SCRIPT}"
PREFIX_EXTRACTION = "$(echo {} | cut -c1) "
FILE_EXTRACTION = "$(echo {} | cut -c3-) "

PREVIEW_COMMAND = (
    "--preview '"
    f"prefix={PREFIX_EXTRACTION}; "
    f"file={FILE_EXTRACTION}; "
    "case \"$prefix\" in "
    "S) git diff --cached --color=always -- \"$file\" | bat --language=Diff ;; "
    "U) git diff --color=always -- \"$file\" | bat --language=Diff ;; "
    "?) bat \"$file\" ;; "
    "esac'"
)

PATCH_COMMAND = (
    f"prefix={PREFIX_EXTRACTION}; "
    f"file={FILE_EXTRACTION}; "
    "case \"$prefix\" in "
    "S) git reset -p \"$file\" ;; "
    "U) git add -p \"$file\" ;; "
    "?) git add --intent-to-add \"$file\" && git add -p \"$file\" ;; "
    "esac"
)
TMUX_POPUP = "tmux display-popup -w 60% -h 60% -d \"$(git rev-parse --show-toplevel)\" -E "

class StatusPage:
    def __init__(self):
        self._base_command = (
            f"{GIT_STATUS_COMMAND} | fzf --ansi --preview-window=right:70% --reverse --cycle "
            f"{PREVIEW_COMMAND} --footer='Git Status' "
            f"--bind 'alt-s:execute-silent(git add {FILE_EXTRACTION})+reload-sync({GIT_STATUS_COMMAND})+down' "
            f"--bind 'alt-S:execute-silent(git add -u)+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-u:execute-silent(git restore --staged {FILE_EXTRACTION})+reload-sync({GIT_STATUS_COMMAND})+down' "
            f"--bind 'alt-U:execute-silent(git restore --staged .)+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-k:execute-silent(git checkout HEAD {FILE_EXTRACTION})+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-K:execute-silent(rm -rf {FILE_EXTRACTION})+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-p:execute({PATCH_COMMAND})+reload-sync({GIT_STATUS_COMMAND})' "
            f"--bind 'alt-e:execute($EDITOR {FILE_EXTRACTION})' "
            f"--bind 'alt-c:execute-silent({TMUX_POPUP} bash {COMMIT_ACTIONS} commit_changes {{}})+reload-sync({GIT_STATUS_COMMAND})' "\
            f"--bind 'alt-l:become(python3 {LOG_SCRIPT})' "\
            "--bind 'alt-t:execute-silent(tmux popup -w 60% -h 60% -d $(git rev-parse --show-toplevel))' "\
            "--bind=tab:down,shift-tab:up "\
            f"--bind 'alt-r:become(python3 {REPO_SCRIPT})' "
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
    StatusPage().run()
