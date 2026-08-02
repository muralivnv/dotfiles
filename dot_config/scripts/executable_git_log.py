#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = ["pygit2"]
# ///

import subprocess
from typing import Optional, Tuple
from argparse import ArgumentParser
from pathlib import Path

import pygit2

DELIMITER               = "@"
PICKER_ESC_RET_CODE     = 130
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


HIDE_COLS = 300

# Bash, like the ${} expansions and here-strings these commands already use.
SPLIT = "sel={{@SELECTION@}}; p=${sel##*$'\\t'}; k=${p#*@}; "


def _payload(selection: str) -> list[str]:
    return selection.rstrip("\n").rsplit("\t", 1)[-1].split(DELIMITER, 1)


def get_selected_line(selection: str) -> Optional[int]:
    try:
        return int(_payload(selection)[0])
    except (IndexError, ValueError):
        return None


def get_key(selection: str) -> str:
    parts = _payload(selection)
    return parts[1] if len(parts) > 1 else ""


def run_picker(producer: str, picker: list, pos: Optional[int] = None) -> Tuple[bool, str]:
    rows = subprocess.run(["bash", "-c", producer], capture_output=True, text=True).stdout
    if pos:
        picker = picker + ["--initial-list-pos", str(pos)]
    picked = subprocess.run(picker, input=rows, text=True, capture_output=True)
    if picked.returncode not in (0, 1, PICKER_ESC_RET_CODE):
        exit(picked.returncode)
    if picked.returncode != 0:
        return False, ""
    return True, picked.stdout.strip()


class BranchPage:
    """Rows are display then LINE@BRANCH_NAME."""

    def __init__(self):
        footer = (
            "Branch History\n"
            "Alt +  b:Checkout • c:Create • x:Reset    • k:Delete   • K:ForceDel • f:Fetch\n"
            "       q:Commit   • g:Reload • t:TmuxPane • r:RepoMenu • F:PullReb  • P:Push"
        )

        self._last_pos: Optional[int] = None
        self._picker = [
            "tooey", "--ansi",
            "--prompt", "[ Branch ] ❯ ",
            "--footer", footer,
            "--query-process-command", "gai --no-color -f {{@QUERY@}}",
            "--preview-command", SPLIT + f'{GIT_LOG_BASE_COMMAND} "$k"',
            "--preview-dir", "bottom",
            "--preview-size", "70",
            "--reload-command", GIT_BRANCH_BASE_COMMAND,
            "--action", "alt-b:Checkout=" + SPLIT + f'{TMUX_POPUP} uv run {BRANCH_ACTIONS} checkout_branch "$k"',
            "--action", "alt-x:Reset=" + SPLIT + f'{TMUX_POPUP} uv run {BRANCH_ACTIONS} reset_branch "$k"',
            "--action", "alt-k:Delete=" + SPLIT + f'{TMUX_POPUP} uv run {BRANCH_ACTIONS} delete_branch "$k"',
            "--action", "alt-K:ForceDel=" + SPLIT + f'{TMUX_POPUP} uv run {BRANCH_ACTIONS} force_delete_branch "$k"',
            "--action", "alt-c:Create=" + SPLIT + f'{TMUX_POPUP} uv run {BRANCH_ACTIONS} create_branch "$k"',
            "--action", f"alt-f:Fetch={TMUX_POPUP} git fetch --all | less -XR",
            "--action", f"alt-F:PullRebase={TMUX_POPUP} uv run {BRANCH_ACTIONS} pull_rebase",
            "--action", f"alt-P:Push={TMUX_POPUP} uv run {COMMIT_ACTIONS} push_changes",
            "--action", "alt-g:Reload=true",
            "--action", f"alt-t:TmuxPane={TMUX_PANE}",
            "--action", f"alt-q:Commit==uv run {COMMIT_SCRIPT}",
            "--action", f"alt-r:RepoMenu==uv run {REPO_SCRIPT}",
        ]

    def run(self, query: Optional[str] = None) -> Tuple[bool, str]:
        ok, line = run_picker(GIT_BRANCH_BASE_COMMAND, self._picker, self._last_pos)
        if not ok:
            return False, ""
        self._last_pos = get_selected_line(line)
        return True, get_key(line) or ""


class LogPage:
    def __init__(self, log_limit: int):
        self._last_pos: Optional[int] = None
        self._base_command: str = GIT_LOG_BASE_COMMAND + f" -n{log_limit} "
        self._picker = [
            "tooey", "--ansi",
            "--prompt", "[ Log ] ❯ ",
            "--query-process-command", "gai --no-color -f {{@QUERY@}}",
            "--preview-command", SPLIT + 'git show "$k" | bat --color=always --language=Diff',
            "--preview-dir", "bottom",
            "--preview-size", "70",
            "--action", "alt-b:Checkout=" + SPLIT + f'{TMUX_POPUP} uv run {COMMIT_ACTIONS} checkout_commit "$k"',
            "--action", "alt-x:SoftReset=" + SPLIT + f'{TMUX_POPUP} uv run {COMMIT_ACTIONS} soft_reset_to_commit "$k"',
            "--action", "alt-X:HardReset=" + SPLIT + f'{TMUX_POPUP} uv run {COMMIT_ACTIONS} hard_reset_to_commit "$k"',
            "--action", "alt-A:CherryPick=" + SPLIT + f'{TMUX_POPUP} uv run {COMMIT_ACTIONS} cherry_pick "$k"',
            "--action", "alt-a:CherryPickNoCommit=" + SPLIT + f'{TMUX_POPUP} uv run {COMMIT_ACTIONS} cherry_pick_no_commit "$k"',
            "--action", "alt-d:OpenDiff=!" + SPLIT + 'git show $k > /tmp/$k.diff && $EDITOR /tmp/$k.diff',
            "--action", f"alt-t:TmuxPane={TMUX_PANE}",
            "--action", f"alt-r:RepoMenu==uv run {REPO_SCRIPT}"
        ]

    def run(self, branch: str = "--all") -> Tuple[bool, str]:
        # The footer names the branch, so it is built per run rather than in __init__.
        footer = (
            f"Branch: {branch}\n"
            "Alt +  b:Checkout • x:SoftReset • X:HardReset • A:CherryPick • a:CherryPick(NoCommit)\n"
            "       d:OpenDiff • t:TmuxPane  • r:RepoMenu"
        )
        producer = f"{self._base_command}{branch} | {GIT_LOG_FMT_COMMAND}"
        picker = self._picker + ["--reload-command", producer, "--footer", footer]
        ok, line = run_picker(producer, picker, self._last_pos)
        if not ok:
            return False, ""
        self._last_pos = get_selected_line(line)
        return True, get_key(line) or "HEAD"


class DiffPage:
    def __init__(self):
        self._last_pos: Optional[int] = None
        self._picker_base = [
            "tooey", "--ansi",
            "--query-process-command", "gai --no-color -f {{@QUERY@}}",
            "--preview-dir", "bottom",
            "--preview-size", "70",
            "--footer", "Alt +  t:TmuxPane • r:RepoMenu • o:OpenFile • d:OpenDiff",
            "--action", f"alt-t:TmuxPane={TMUX_PANE}",
            "--action", f"alt-r:RepoMenu==uv run {REPO_SCRIPT}",
        ]

    def run(self, commit_hash: Optional[str] = None) -> Tuple[bool, str]:
        if not commit_hash:
            return False, ""

        header_line = subprocess.check_output(
            ['git', 'log', '-1', '--format=%h | %an | %ad | %s', '--date=short', commit_hash],
            text=True
        ).strip()

        # awk builds the padding with %*s rather than carrying a 300-space literal.
        producer = (f"{{ printf '%s\n' '(commit info)'; "
                    f"git show --pretty= --name-only {commit_hash}; }} | "
                    f"awk -v w={HIDE_COLS} "
                    f"""'NF{{n++;printf "%s%*s\\t%d@%s\\n", $0, w, "", n, $0}}'""")

        preview = SPLIT + (
            f'if [ "$k" = "(commit info)" ]; then git show {commit_hash} -s | bat --color=always; '
            f'else git show --format= {commit_hash} -- "$k" | bat --color=always --language=Diff; fi'
        )
        alt_o_cmd = SPLIT + f'if [ "$k" != "(commit info)" ]; then f=$(basename "$k"); git show "{commit_hash}:$k" > "/tmp/$f" && $EDITOR "/tmp/$f"; fi'
        alt_d_cmd = SPLIT + f'if [ "$k" != "(commit info)" ]; then f=$(basename "$k"); git diff {commit_hash}^! -- "$k" > "/tmp/$f.diff" && $EDITOR "/tmp/$f.diff"; fi'

        # The commit line goes in the header, where fzf put it.
        picker = self._picker_base + [
            "--header", header_line,
            "--preview-command", preview,
            "--reload-command", producer,
            "--action", f"alt-o:Open=!{alt_o_cmd}",
            "--action", f"alt-d:Diff=!{alt_d_cmd}"
        ]
        ok, line = run_picker(producer, picker, self._last_pos)
        if not ok:
            return False, ""
        self._last_pos = get_selected_line(line)
        return True, commit_hash


if __name__ == "__main__":
    cli_args = ArgumentParser(description="Interactive git log")
    cli_args.add_argument("-n", help="log limit", required=False, type=int, default=100, dest="n")
    parsed_args, _ = cli_args.parse_known_args()

    if not pygit2.discover_repository("."):
        print("[ERROR] Not a git repository")
        exit(1)

    tab0 = BranchPage()
    tab1 = LogPage(parsed_args.n)
    tab2 = DiffPage()

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
