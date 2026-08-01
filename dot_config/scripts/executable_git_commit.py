#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = ["pygit2"]
# ///

import subprocess
from pathlib import Path

import pygit2

PICKER_ESC_RET_CODE = 130
DELIMITER          = "@"
SCRIPT_DIR         = Path(__file__).resolve().parent
REPO_SCRIPT        = SCRIPT_DIR / "git_repo_list.py"
LOG_SCRIPT         = SCRIPT_DIR / "git_log.py"
STATUS_SCRIPT      = SCRIPT_DIR / "lib/git_status.py"
COMMIT_ACTIONS     = SCRIPT_DIR / "lib/commit_actions.py"
TMUX_POPUP         = r'tmux display-popup -w 60% -h 60% -d "$(git rev-parse --show-toplevel)" -E '
TMUX_PANE          = r'tmux split-window -v -p 40 -c "$(git rev-parse --show-toplevel)" '
GIT_STATUS_COMMAND = f"uv run {STATUS_SCRIPT}"

# git_status.py emits <display><padding>\t<status>@<path>
SPLIT = "sel={{@SELECTION@}}; p=${sel##*$'\\t'}; st=${p%%@*}; f=${p#*@}; "

PREVIEW_COMMAND = SPLIT + (
    'case "$st" in '
    'S) git diff --cached -- "$f" | bat --color=always --language=Diff ;; '
    'U|C) git diff -- "$f" | bat --color=always --language=Diff ;; '
    '"?") git diff --no-index /dev/null -- "$f" | bat --color=always --language=Diff ;; '
    "esac"
)

PATCH_COMMAND = SPLIT + (
    'case "$st" in '
    'S) git reset -p -- "$f" ;; '
    'U|C) git add -p -- "$f" ;; '
    '"?") git add --intent-to-add -- "$f" && git add -p -- "$f" ;; '
    "esac"
)


class StatusPage:
    def __init__(self):
        footer = (
            "Git Status\n"
            "Alt +  s:Stage      • S:StageAll • u:Unstage\n"
            "       U:UnstageAll • p:Patch    • k:Restore\n"
            "       K:Delete     • o:Editor   • c:Commit\n"
            "       P:Push       • l:LogMenu  • g:Reload\n"
            "       t:TmuxPane   • r:RepoMenu"
        )

        self._command = [
            "tooey",
            "--ansi",
            "--prompt", " [ Status ] ❯ ",
            "--footer", footer,
            "--query-process-command", "gai --no-color -f {{@QUERY@}}",
            "--preview-command", PREVIEW_COMMAND,
            "--preview-dir", "right",
            "--preview-size", "70",
            "--reload-command", GIT_STATUS_COMMAND,
            "--action", "alt-s:Stage=" + SPLIT + 'git add -- "$f"',
            "--action", "alt-S:StageAll=git add -u",
            "--action", "alt-u:Unstage=" + SPLIT + 'git restore --staged -- "$f"',
            "--action", "alt-U:UnstageAll=git restore --staged .",
            "--action", "alt-k:Restore=" + SPLIT +
                        'read -p "Restore $f? [y/N] " c; case "$c" in y) git restore -- "$f";; esac',
            "--action", "alt-K:Delete=" + SPLIT +
                        'read -p "Delete $f? [y/N] " c; case "$c" in y) rm -rf -- "$f";; esac',
            "--action", "alt-p:Patch=" + PATCH_COMMAND,
            "--action", "alt-g:Reload=true",
            "--action", "alt-o:Editor=" + SPLIT + '$EDITOR "$f"',
            "--action", f"alt-c:Commit=uv run {COMMIT_ACTIONS} commit_changes",
            "--action", f"alt-P:Push={TMUX_POPUP} uv run {COMMIT_ACTIONS} push_changes",
            "--action", f"alt-t:TmuxPane={TMUX_PANE}",
            "--action", f"alt-l:LogMenu==uv run {LOG_SCRIPT}",
            "--action", f"alt-r:RepoMenu==uv run {REPO_SCRIPT}",
        ]

    def run(self):
        rows = subprocess.run(["bash", "-c", GIT_STATUS_COMMAND],
                              capture_output=True, text=True).stdout
        picked = subprocess.run(self._command, input=rows, text=True)
        if picked.returncode not in (0, 1, PICKER_ESC_RET_CODE):
            exit(picked.returncode)
        return picked.returncode == 0


if __name__ == "__main__":
    if not pygit2.discover_repository("."):
        print("[ERROR] Not inside a Git repository.")
        exit(1)
    StatusPage().run()
