#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

import subprocess
from typing import Optional, Tuple
from argparse import ArgumentParser
import socket
import os

DELIMITER               = "@"
FZF_ESC_RET_CODE        = 130
SCRIPT_DIR              = os.path.dirname(os.path.abspath(__file__))
REPO_SCRIPT             = os.path.join(SCRIPT_DIR, "git_repo_list.py")
COMMIT_SCRIPT           = os.path.join(SCRIPT_DIR, "git_commit.py")
GIT_BRANCH_SCRIPT       = os.path.join(SCRIPT_DIR, "lib/git_branch.py")
BRANCH_ACTIONS          = os.path.join(SCRIPT_DIR, "lib/branch_actions.py")
COMMIT_ACTIONS          = os.path.join(SCRIPT_DIR, "lib/commit_actions.py")
BRANCH_EXTRACT_COMMAND  = r'gai -r "#^\d+@([A-Za-z0-9._\/-]+).*#\$1#"'
COMMIT_EXTRACT_COMMAND  = r'gai -r "#^\d+@(?:.*)\*\s+([a-z0-9]{4,}).*#\$1#"'
GIT_BRANCH_BASE_COMMAND = fr'uv run {GIT_BRANCH_SCRIPT} | gai -f "\w" -v -d {DELIMITER}'
GIT_LOG_BASE_COMMAND    = (r'git log --oneline --graph --decorate --color '
                           r'--pretty=format:"%C(auto)%h%Creset %C(bold cyan)%cn%Creset %C(green)%aD%Creset %s"')
# TMUX_POPUP              = r'tmux display-popup -w 60% -h 60% -d "$(git rev-parse --show-toplevel)" -DE '
TMUX_POPUP              = r'tmux split-window -v -p 40 -c "$(git rev-parse --show-toplevel)" '

def get_selected_line(selection: str) -> Optional[int]:
    items = selection.split(DELIMITER)
    try:
        ret = int(items[0].strip())
        return ret
    except Exception:
        pass
    return None

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

class BranchPage:
    def __init__(self, port: int):
        reload_cmd: str = f'curl -XPOST localhost:{port} -d "reload({GIT_BRANCH_BASE_COMMAND})" '
        self._vis_command: str = ( f" | "
                                   f"fzf --listen {port} --delimiter '{DELIMITER}' --reverse --ansi --with-nth=2.. --preview '{GIT_LOG_BASE_COMMAND} "
                                   f"$(echo {{}} | {BRANCH_EXTRACT_COMMAND}) ' --preview-window=bottom:70% "
                                   f"--bind 'alt-b:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} checkout_branch {{}})' "
                                   f"--bind 'alt-x:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} reset_branch {{}})' "
                                   f"--bind 'alt-k:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} delete_branch {{}})' "
                                   f"--bind 'alt-K:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} force_delete_branch {{}})' "
                                   f"--bind 'alt-c:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} create_branch {{}})' "
                                   f"--bind 'alt-f:execute-silent({TMUX_POPUP} git fetch --all)' "
                                   f"--bind 'alt-F:execute-silent({TMUX_POPUP} uv run {BRANCH_ACTIONS} pull_rebase)' "
                                   f"--bind 'alt-P:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} push_changes)' "
                                   f"--bind 'alt-g:reload-sync({GIT_BRANCH_BASE_COMMAND})' "
                                   f"--bind 'alt-q:become(uv run {COMMIT_SCRIPT})' "
                                   f"--bind 'alt-t:execute-silent({TMUX_POPUP})' "
                                   f"--bind 'alt-r:become(uv run {REPO_SCRIPT})' "
                                   "--bind=tab:down,shift-tab:up ")
        self._last_selected_line: int = 0

    def run(self, query: Optional[str] = None) -> Tuple[bool, str]:
        try:
            vis_cmd = self._vis_command + f" --bind 'load:pos({self._last_selected_line})' --footer 'Branch History'"
            output = subprocess.check_output(GIT_BRANCH_BASE_COMMAND + vis_cmd, shell=True, universal_newlines=True)
            selected_line = get_selected_line(output)
            if selected_line is not None:
                self._last_selected_line = selected_line
            branch = self._get_branch_name(output)
            if branch is None:
                branch = ""
            return True, branch
        except subprocess.CalledProcessError as e:
            if e.returncode != FZF_ESC_RET_CODE:
                exit(e.returncode)
        return False, ""

    def _get_branch_name(self, selection: str) -> Optional[str]:
        try:
            branch = selection.split(DELIMITER)[1].split(" ")[0].strip()
            return branch
        except Exception:
            pass
        return None

class LogPage:
    def __init__(self, log_limit: int, port:int):
        self._base_command: str = GIT_LOG_BASE_COMMAND + f" -n{log_limit} "
        self._vis_command: str  = (f" | gai -f \"\\w\" -v -d {DELIMITER} | "
                                   f"fzf --listen {port} --delimiter '{DELIMITER}' --reverse --ansi --with-nth=2.. "
                                   f"--preview 'echo {{}} | {COMMIT_EXTRACT_COMMAND} | xargs git show | bat --color=always --language=Diff ' "
                                   "--preview-window=bottom:70% "
                                   f"--bind 'alt-b:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} checkout_commit {{}})' "
                                   f"--bind 'alt-x:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} soft_reset_to_commit {{}})' "
                                   f"--bind 'alt-X:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} hard_reset_to_commit {{}})' "
                                   f"--bind 'alt-A:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} cherry_pick {{}})' "
                                   f"--bind 'alt-a:execute-silent({TMUX_POPUP} uv run {COMMIT_ACTIONS} cherry_pick_no_commit {{}})' "
                                   f"--bind 'alt-t:execute-silent({TMUX_POPUP})' "
                                   f"--bind 'alt-r:become(uv run {REPO_SCRIPT})' "
                                   f"--bind 'alt-l:reload-sync(git log --oneline --graph --decorate --color --branches --all | nl -w1 -s\"{DELIMITER}\")+bg-transform-header(Full log)' "
                                   "--bind=tab:down,shift-tab:up ")

        self._last_selected_line: int = 0

    def run(self, branch: str = "--all") -> Tuple[bool, str]:
        try:
            log_cmd = self._base_command +  branch
            vis_cmd = self._vis_command + f" --bind 'load:pos({self._last_selected_line})' " +\
                      f"--header 'Branch: {branch}' " + \
                      f"--bind 'alt-g:reload-sync({log_cmd} | gai -f \"\\w\" -v -d {DELIMITER})+bg-transform-header(Branch: {branch})' "
                      
            output = subprocess.check_output(log_cmd + vis_cmd, shell=True, universal_newlines=True)
            selected_line = get_selected_line(output)
            if selected_line is not None:
                self._last_selected_line = selected_line
            commit_hash = self._get_commit_hash(output)
            if commit_hash is None:
                commit_hash = "HEAD"
            return True, commit_hash
        except subprocess.CalledProcessError as e:
            if e.returncode != FZF_ESC_RET_CODE:
                exit(e.returncode)
        return False, ""

    def _get_commit_hash(self, selection: str) -> str:
        try:
            hash = selection.split(DELIMITER)[1].strip().split(' ')[1]
            return hash
        except Exception:
            pass
        return None

class DiffPage:
    def __init__(self, port:int):
        self._base_command: str = "git show --pretty= --name-only "
        self._vis_command: str = (f" | gai -f \"\\w\" -v -d {DELIMITER} | "
                                  f"fzf --listen {port} --delimiter '{DELIMITER}' --reverse --ansi --with-nth=2.. "
                                  "--preview-window=bottom:70% ")
        self._last_selected_line: int = 0

    def run(self, commit_hash: Optional[str] = None) -> Tuple[bool, str]:
        if not commit_hash:
            return False, ""

        try:
            vis_cmd = self._vis_command + f" --bind 'load:pos({self._last_selected_line})' " + \
                      f"--preview 'git show --format= {commit_hash} {{2}} | bat --color=always --language=Diff' "\
                      f"--header-label 'Info' --bind 'focus:+bg-transform-header:git show {commit_hash} -s' "\
                      f"--bind 'alt-t:execute-silent({TMUX_POPUP})' "\
                      f"--bind 'alt-r:become(uv run {REPO_SCRIPT})' "\
                      "--bind=tab:down,shift-tab:up "

            output = subprocess.check_output(self._base_command + commit_hash + vis_cmd,
                                             shell=True, universal_newlines=True)
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

    free_port = get_free_port()
    tab0 = BranchPage(port=free_port)
    tab1 = LogPage(parsed_args.n, port=free_port)
    tab2 = DiffPage(port=free_port)

    payloads = dict(
        tab0=tab0,
        tab1=tab1,
        tab2=tab2
    )

    payloads_input = dict(
        tab0="",
        tab1="--all",
        tab2=""
    )

    task_graph = dict(
        tab0 = dict(
            on_enter = "tab1",
            on_esc = None,
        ),
        tab1 = dict(
            on_enter = "tab2",
            on_esc = "tab0",
        ),
        tab2 = dict(
            on_enter = "tab2",
            on_esc = "tab1",
        )
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
