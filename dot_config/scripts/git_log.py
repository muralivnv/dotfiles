import subprocess
from typing import Optional, Tuple
from argparse import ArgumentParser
import os

DELIMITER               = "@"
FZF_ESC_RET_CODE        = 130
GIT_BRANCH_BASE_COMMAND = "git for-each-ref --count=10 --sort=-authordate --color --format=\"%(align:1,left)%(color:red)%(HEAD) "\
                          "%(end)%(color:reset)%(color:green)%(align:50,left)%(refname:lstrip=2)%(end) %(color:yellow)%(align:8,left)"\
                          "%(objectname:short)%(end)%(color:reset) %(color:cyan) %(align:60,left)%(contents:subject)%(end)%(color:reset) "\
                          f"%(align:20,left)%(color:blue)%(authorname)%(color:reset)%(end) %(align:20,left)%(committerdate:relative)%(end)\" | nl -w1 -s\"{DELIMITER}\""

GIT_LOG_BASE_COMMAND    = "git log --oneline --graph --decorate --color --pretty=format:\"%C(auto)%h%Creset %C(bold cyan)%cn%Creset %C(green)%aD%Creset %s\""
CAPTURE_AND_SHOW_ERROR  = f"1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt"
CREATE_BRANCH_PARENT_PROMPT = "gum input --header.foreground=\"#00ff00\" --header=\"Create branch from\" --no-show-help"
CREATE_BRANCH_NAME_PROMPT = "gum input --header.foreground=\"#00ff00\" --header=\"Branch name\" --no-show-help"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_SCRIPT = os.path.join(SCRIPT_DIR, "git_repo_list.py")
COMMIT_SCRIPT = os.path.join(SCRIPT_DIR, "git_commit.py")

def get_selected_line(selection: str) -> Optional[int]:
    items = selection.split(DELIMITER)
    try:
        ret = int(items[0].strip())
        return ret
    except:
        pass
    return None

class BranchPage:
    def __init__(self):
        self._vis_command: str = f" | " \
                                 f"fzf --delimiter '{DELIMITER}' --reverse --ansi --with-nth=2.. --preview '{GIT_LOG_BASE_COMMAND} " \
                                 "$(echo {} |  purl -extract \"#^\d+@[\*\s+]\s+([A-Za-z0-9._\/-]+)#\$1#\") ' --preview-window=bottom:70% " \
                                 "--bind 'alt-b:execute(" \
                                                   f"BR=$(echo {{}} |  purl -extract \"#^\d+{DELIMITER}[\*\s+]\s+([A-Za-z0-9._\/-]+)#\$1#\" | sed \"s#^origin/##\"); " \
                                                   f"gum confirm \"Checkout >>>> $BR <<<< ?\" --no-show-help && $(git switch \"$BR\" {CAPTURE_AND_SHOW_ERROR}))+reload-sync({GIT_BRANCH_BASE_COMMAND})' "\
                                 "--bind 'alt-k:execute(" \
                                                   f"BR=$(echo {{}} |  purl -extract \"#^\d+{DELIMITER}[\*\s+]\s+([A-Za-z0-9._\/-]+)#\$1#\" | sed \"s#^origin/##\"); " \
                                                   f"gum confirm \"Delete branch >>>> $BR? <<<< \" --no-show-help && $(git branch -d \"$BR\" {CAPTURE_AND_SHOW_ERROR}))+reload-sync({GIT_BRANCH_BASE_COMMAND})' "\
                                 "--bind 'alt-K:execute(" \
                                                   f"BR=$(echo {{}} |  purl -extract \"#^\d+{DELIMITER}[\*\s+]\s+([A-Za-z0-9._\/-]+)#\$1#\" | sed \"s#^origin/##\"); " \
                                                   f"gum confirm \"Force Delete branch >>>> $BR? <<<< \" --no-show-help && $(git branch -D \"$BR\" {CAPTURE_AND_SHOW_ERROR}))+reload-sync({GIT_BRANCH_BASE_COMMAND})' "\
                                 "--bind 'alt-c:execute(" \
                                                   f"BR=$(echo {{}} |  purl -extract \"#^\d+{DELIMITER}[\*\s+]\s+([A-Za-z0-9._\/-]+)#\$1#\" | sed \"s#^origin/##\"); " \
                                                   f"PARENT=$({CREATE_BRANCH_PARENT_PROMPT} --value $BR) && "\
                                                   f"CHILD=$({CREATE_BRANCH_NAME_PROMPT}) && "\
                                                   f"$(git branch $CHILD $PARENT {CAPTURE_AND_SHOW_ERROR}))+reload-sync({GIT_BRANCH_BASE_COMMAND})' "\
                                 f"--bind 'alt-l:reload-sync(git log --oneline --graph --decorate --color --branches | nl -w1 -s\"{DELIMITER}\")+bg-transform-header(Full log)' "\
                                 f"--bind 'alt-f:execute(git fetch --all)+reload-sync({GIT_BRANCH_BASE_COMMAND})' "\
                                 f"--bind 'alt-F:execute(git pull --rebase)+reload-sync({GIT_BRANCH_BASE_COMMAND})' "\
                                 f"--bind 'alt-P:execute(git push)+reload-sync({GIT_BRANCH_BASE_COMMAND})' "\
                                 f"--bind 'alt-s:become(python3 {COMMIT_SCRIPT})' "\
                                 "--bind 'alt-t:execute-silent(tmux popup -w 60% -h 60% -d $(git rev-parse --show-toplevel))' "\
                                 f"--bind 'alt-r:become(python3 {REPO_SCRIPT})' "\
                                 "--bind=tab:down,shift-tab:up "
                                 
        self._last_selected_line: int = 0

    def run(self, query: Optional[str] = None) -> Tuple[bool, str]:
        try:
            vis_cmd = self._vis_command + f" --bind 'load:pos({self._last_selected_line})' --footer 'Branch History'"
            output = subprocess.check_output(GIT_BRANCH_BASE_COMMAND + vis_cmd, shell=True, universal_newlines=True)
            selected_line = get_selected_line(output)
            if selected_line is not None:
                self._last_selected_line = selected_line
            return True, self._get_branch_name(output)
        except subprocess.CalledProcessError as e:
            if e.returncode != FZF_ESC_RET_CODE:
                exit(e.returncode)
        return False, ""

    def _get_branch_name(self, selection: str) -> str:
        branch = selection.split(DELIMITER)[-1].split(" ")[-1].strip()
        branch = branch.replace("remotes/", "")
        return branch

class LogPage:
    def __init__(self, log_limit: int):
        self._base_command: str = GIT_LOG_BASE_COMMAND + f" -n{log_limit} "
        self._vis_command: str  = f" | nl -w1 -s\"{DELIMITER}\" | " \
                                  f"fzf --delimiter '{DELIMITER}' --reverse --ansi --with-nth=2.. "\
                                  "--preview 'echo {} | purl -extract \"#\*\s+([a-z0-9]{4,})#\$1#\" | xargs git show | bat --color=always --language=Diff ' "\
                                  "--preview-window=bottom:70% "\
                                  "--bind 'alt-b:execute("\
                                                  "COMMIT=$(echo {} | purl -extract \"#\*\s+([a-z0-9]{4,})#\$1#\"); "\
                                                  f"gum confirm \"Checkout >>>> $COMMIT <<<< ?\" --no-show-help && $(git checkout \"$COMMIT\" {CAPTURE_AND_SHOW_ERROR}) )' "\
                                  "--bind 'alt-x:execute("\
                                                  "COMMIT=$(echo {} | purl -extract \"#\*\s+([a-z0-9]{4,})#\$1#\"); BR=$(git branch --show-current); "\
                                                  f"gum confirm \"Soft reset $BR to >>> $COMMIT <<<< ?\" --no-show-help && $(git reset --soft \"$COMMIT\" {CAPTURE_AND_SHOW_ERROR}) )' "\
                                  "--bind 'alt-X:execute("\
                                                  "COMMIT=$(echo {} | purl -extract \"#\*\s+([a-z0-9]{4,})#\$1#\"); BR=$(git branch --show-current); "\
                                                  f"gum confirm \"Hard reset $BR to >>> $COMMIT <<<< ?\" --no-show-help && $(git reset --hard \"$COMMIT\" {CAPTURE_AND_SHOW_ERROR}) )' "\
                                  "--bind 'alt-A:execute("\
                                                  "COMMIT=$(echo {} | purl -extract \"#\*\s+([a-z0-9]{4,})#\$1#\"); "\
                                                  f"gum confirm \"Cherry-pick >>> $COMMIT <<<< ?\" --no-show-help && $(git cherry-pick \"$COMMIT\" {CAPTURE_AND_SHOW_ERROR}) )' "\
                                  "--bind 'alt-a:execute("\
                                                  "COMMIT=$(echo {} | purl -extract \"#\*\s+([a-z0-9]{4,})#\$1#\"); "\
                                                  f"gum confirm \"Apply changes from >>> $COMMIT <<<< ?\" --no-show-help && $(git cherry-pick --no-commit \"$COMMIT\" {CAPTURE_AND_SHOW_ERROR}) )' "\
                                  f"--bind 'alt-l:reload-sync(git log --oneline --graph --decorate --color --branches | nl -w1 -s\"{DELIMITER}\")+bg-transform-header(Full log)' "\
                                  "--bind 'alt-t:execute-silent(tmux popup -w 60% -h 60% -d $(git rev-parse --show-toplevel))' "\
                                  f"--bind 'alt-r:become(python3 {REPO_SCRIPT})' "\
                                  "--bind=tab:down,shift-tab:up "

        self._last_selected_line: int = 0

    def run(self, branch: str = "--all") -> Tuple[bool, str]:
        try:
            log_cmd = self._base_command +  branch
            vis_cmd = self._vis_command + f" --bind 'load:pos({self._last_selected_line})' " +\
                      f"--header 'Branch: {branch}' "
            output = subprocess.check_output(log_cmd + vis_cmd, shell=True, universal_newlines=True)
            selected_line = get_selected_line(output)
            if selected_line is not None:
                self._last_selected_line = selected_line
            return True, self._get_commit_hash(output)
        except subprocess.CalledProcessError as e:
            if e.returncode != FZF_ESC_RET_CODE:
                exit(e.returncode)
        return False, ""

    def _get_commit_hash(self, selection: str) -> str:
        hash = selection.split(DELIMITER)[1].strip().split(' ')[1]
        return hash

class DiffPage:
    def __init__(self):
        self._base_command: str = "git show --pretty= --name-only "
        self._vis_command: str = f" | nl -w1 -s\"{DELIMITER}\" | " \
                                 f"fzf --delimiter '{DELIMITER}' --reverse --ansi --with-nth=2.. " \
                                 "--preview-window=bottom:70% "
        self._last_selected_line: int = 0

    def run(self, commit_hash: Optional[str] = None) -> Tuple[bool, str]:
        if not commit_hash:
            return False, ""

        try:
            vis_cmd = self._vis_command + f" --bind 'load:pos({self._last_selected_line})' " + \
                      f"--preview 'git show --format= {commit_hash} {{2}} | bat --color=always --language=Diff' "\
                      f"--header-label 'Info' --bind 'focus:+bg-transform-header:git show {commit_hash} -s' "\
                      "--bind 'alt-t:execute-silent(tmux popup -w 60% -h 60% -d $(git rev-parse --show-toplevel))' "\
                      f"--bind 'alt-r:become(python3 {REPO_SCRIPT})' "\
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

    tab0 = BranchPage()
    tab1 = LogPage(parsed_args.n)
    tab2 = DiffPage()

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
