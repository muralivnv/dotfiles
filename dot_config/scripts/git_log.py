#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = ["pygit2"]
# ///

import shlex
import subprocess
from typing import Optional, Tuple
from argparse import ArgumentParser
import socket
from pathlib import Path

import pygit2

DELIMITER               = "@"
FZF_ESC_RET_CODE        = 130
SCRIPT_DIR              = Path(__file__).resolve().parent
REPO_SCRIPT             = SCRIPT_DIR / "git_repo_list.py"
COMMIT_SCRIPT           = SCRIPT_DIR / "git_commit.py"
GIT_BRANCH_SCRIPT       = SCRIPT_DIR / "lib/git_branch.py"
GIT_LOG_FMT             = SCRIPT_DIR / "lib/git_log_fmt.py"
BRANCH_ACTIONS          = SCRIPT_DIR / "lib/branch_actions.py"
COMMIT_ACTIONS          = SCRIPT_DIR / "lib/commit_actions.py"

GIT_BRANCH_BASE_COMMAND = f'uv run {GIT_BRANCH_SCRIPT}'
GIT_LOG_BASE_COMMAND    = (r'git log --oneline --graph --decorate --color '
                           r'--pretty=format:"%C(auto)%h%Creset %C(bold cyan)%cn%Creset %C(green)%aD%Creset %s"')
GIT_LOG_FMT_COMMAND     = f'uv run {GIT_LOG_FMT}'
TMUX_POPUP              = r'tmux display-popup -w 60% -h 60% -d "$(git rev-parse --show-toplevel)" -E '
TMUX_PANE               = r'tmux split-window -v -p 40 -c "$(git rev-parse --show-toplevel)" '


def get_selected_line(selection: str) -> Optional[int]:
    """Extract line number from field 2 of KEY@LINE@display."""
    parts = selection.split(DELIMITER)
    try:
        return int(parts[1])
    except (IndexError, ValueError):
        return None


def get_key(selection: str) -> str:
    """Extract key from field 1 of KEY@LINE@display."""
    return selection.split(DELIMITER, 1)[0]


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class BranchPage:
    """Format: BRANCH_NAME@LINE@display — {1}=branch, {2}=line, {3..}=display"""

    def __init__(self, port: int):
        footer = (
            "Branch History\n"
            "Alt +  b:Checkout • c:Create • x:Reset • k:Delete • K:ForceDel • f:Fetch • F:PullReb • P:Push\n"
            "       q:Commit • g:Reload • t:TmuxPane • r:RepoMenu • Tab/S-Tab:Navigate"
        )
        
        self._vis_command: str = (
            f" | fzf --listen {port} --delimiter '{DELIMITER}' --reverse --ansi --with-nth=3.. "
            f"--preview '{GIT_LOG_BASE_COMMAND} {{1}} ' --preview-window=bottom:70% "
            f"--footer-border dashed --footer='{footer}' "
            f"--bind 'alt-b:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} checkout_branch {{1}})' "
            f"--bind 'alt-x:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} reset_branch {{1}})' "
            f"--bind 'alt-k:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} delete_branch {{1}})' "
            f"--bind 'alt-K:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} force_delete_branch {{1}})' "
            f"--bind 'alt-c:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} create_branch {{1}})' "
            f"--bind 'alt-f:execute-silent({TMUX_POPUP} git fetch --all | less -XR)' "
            f"--bind 'alt-F:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} pull_rebase)' "
            f"--bind 'alt-P:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} push_changes)' "
            f"--bind 'alt-g:reload-sync({GIT_BRANCH_BASE_COMMAND})' "
            f"--bind 'alt-q:become(uv run {COMMIT_SCRIPT})' "
            f"--bind 'alt-t:execute-silent({TMUX_PANE})' "
            f"--bind 'alt-r:become(uv run {REPO_SCRIPT})' "
            "--bind=tab:down,shift-tab:up "
        )
        self._last_selected_line: int = 0

    def run(self, query: Optional[str] = None) -> Tuple[bool, str]:
        try:
            vis_cmd = self._vis_command + f" --bind 'load:pos({self._last_selected_line})' "
            output = subprocess.check_output(
                GIT_BRANCH_BASE_COMMAND + vis_cmd, shell=True, universal_newlines=True
            )
            selected_line = get_selected_line(output)
            if selected_line is not None:
                self._last_selected_line = selected_line
            return True, get_key(output) or ""
        except subprocess.CalledProcessError as e:
            if e.returncode != FZF_ESC_RET_CODE:
                exit(e.returncode)
        return False, ""


class LogPage:
    """Format: HASH@LINE@display — {1}=hash, {2}=line, {3..}=display"""

    def __init__(self, log_limit: int, port: int):
        self._base_command: str = GIT_LOG_BASE_COMMAND + f" -n{log_limit} "
        self._vis_command: str = (
            f" | {GIT_LOG_FMT_COMMAND} | "
            f"fzf --listen {port} --delimiter '{DELIMITER}' --reverse --ansi --with-nth=3.. "
            f"--preview 'git show {{1}} | bat --color=always --language=Diff' "
            "--preview-window=bottom:70% --footer-border dashed "
            f"--bind 'alt-b:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} checkout_commit {{1}})' "
            f"--bind 'alt-x:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} soft_reset_to_commit {{1}})' "
            f"--bind 'alt-X:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} hard_reset_to_commit {{1}})' "
            f"--bind 'alt-A:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} cherry_pick {{1}})' "
            f"--bind 'alt-a:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} cherry_pick_no_commit {{1}})' "
            f"--bind 'alt-t:execute-silent({TMUX_PANE})' "
            f"--bind 'alt-r:become(uv run {REPO_SCRIPT})' "
            f"--bind 'alt-l:reload-sync(git log --oneline --graph --decorate --color --branches --all "
            f"| {GIT_LOG_FMT_COMMAND})+bg-transform-header(Full log)' "
            "--bind=tab:down,shift-tab:up "
        )
        self._last_selected_line: int = 0

    def run(self, branch: str = "--all") -> Tuple[bool, str]:
        try:
            log_cmd = self._base_command + branch
            
            footer = (
                f"Branch: {branch}\n"
                "Alt +  b:Checkout • x:SoftReset • X:HardReset • A:CherryPick • a:CherryPick(NoCommit)\n"
                "       l:LogAll • g:Reload • t:TmuxPane • r:RepoMenu • Tab/S-Tab:Navigate"
            )
            
            vis_cmd = (
                self._vis_command
                + f" --bind 'load:pos({self._last_selected_line})' "
                + f"--footer '{footer}' "
                + f"--bind 'alt-g:reload-sync({log_cmd} | {GIT_LOG_FMT_COMMAND})+bg-transform-header(Branch: {branch})' "
            )
            output = subprocess.check_output(log_cmd + vis_cmd, shell=True, universal_newlines=True)
            selected_line = get_selected_line(output)
            if selected_line is not None:
                self._last_selected_line = selected_line
            return True, get_key(output) or "HEAD"
        except subprocess.CalledProcessError as e:
            if e.returncode != FZF_ESC_RET_CODE:
                exit(e.returncode)
        return False, ""


class DiffPage:
    """Format: FILENAME@LINE@display — {1}=filename, {2}=line, {3..}=display"""

    def __init__(self, port: int):
        footer = "Alt +  t:TmuxPane • r:RepoMenu • Tab/S-Tab:Navigate"
        
        self._vis_command: str = (
            f" | awk -v d='{DELIMITER}' 'NF{{n++;print $0 d n d $0}}' | "
            f"fzf --listen {port} --delimiter '{DELIMITER}' --reverse --ansi --with-nth=3.. "
            f"--preview-window=bottom:70% --footer-border dashed --footer='{footer}' "
        )
        self._last_selected_line: int = 0

    def run(self, commit_hash: Optional[str] = None) -> Tuple[bool, str]:
        if not commit_hash:
            return False, ""

        try:
            header_line = subprocess.check_output(
                ['git', 'log', '-1', '--format=%h | %an | %ad | %s', '--date=short', commit_hash],
                text=True
            ).strip()

            list_cmd = (f"{{ printf '%s\n' '(commit info)'; "
                        f"git show --pretty= --name-only {commit_hash}; }}")

            vis_cmd = (
                self._vis_command
                + f"--bind 'load:pos({self._last_selected_line})' "
                + f"--header {shlex.quote(header_line)} "
                + f"--preview '"
                + f"if [ {{1}} = \"(commit info)\" ]; then "
                + f"git show {commit_hash} -s | bat --color=always; "
                + f"else "
                + f"git show --format= {commit_hash} -- {{1}} | bat --color=always --language=Diff; "
                + f"fi' "
                + f"--bind 'alt-t:execute-silent({TMUX_PANE})' "
                + f"--bind 'alt-r:become(uv run {REPO_SCRIPT})' "
                + "--bind=tab:down,shift-tab:up "
            )

            output = subprocess.check_output(
                list_cmd + vis_cmd, shell=True, universal_newlines=True
            )
            selected_line = get_selected_line(output)
            if selected_line is not None:
                self._last_selected_line = selected_line
            return True, commit_hash
        except subprocess.CalledProcessError as e:
            if e.returncode != FZF_ESC_RET_CODE:
                exit(e.returncode)
        return False, ""


if __name__ == "__main__":
    cli_args = ArgumentParser(description="Interactive git log")
    cli_args.add_argument("-n", help="log limit", required=False, type=int, default=100, dest="n")
    parsed_args, _ = cli_args.parse_known_args()

    if not pygit2.discover_repository("."):
        print("[ERROR] Not a git repository")
        exit(1)

    free_port = get_free_port()
    tab0 = BranchPage(port=free_port)
    tab1 = LogPage(parsed_args.n, port=free_port)
    tab2 = DiffPage(port=free_port)

    payloads = dict(tab0=tab0, tab1=tab1, tab2=tab2)
    payloads_input = dict(tab0="", tab1="--all", tab2="")
    task_graph = dict(
        tab0=dict(on_enter="tab1", on_esc=None),
        tab1=dict(on_enter="tab2", on_esc="tab0"),
        tab2=dict(on_enter="tab2", on_esc="tab1"),
    )

    key = "tab0"
    while True:
        if key is None:
            break
        task = payloads[key]
        task_input = payloads_input[key]
        success, task_output = task.run(task_input)
        if success:
            key = task_graph[key]["on_enter"]
            payloads_input[key] = task_output
        else:
            key = task_graph[key]["on_esc"]
