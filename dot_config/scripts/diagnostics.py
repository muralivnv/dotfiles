import subprocess
import os
from pathlib import Path
import socket
import shlex
import hashlib
from argparse import ArgumentParser
from watchfiles import watch, DefaultFilter
from threading import Thread, Event

DIAGNOSTICS_CMD_FILE = ".ronin/diagnostics.txt"

FZF_CMD = (
    "fzf --border -i --preview 'bat {1} --highlight-line {2}' --preview-window 'right,+{2}+3/3,~3' "
    "--delimiter : --nth 1 --scrollbar '▍' --bind=tab:down,shift-tab:up --smart-case --cycle "
    "--style=full:line --layout=reverse --footer 'Error' --bind 'focus:+bg-transform-footer:echo {4} | fold -s -w 100' "
    "--color 'footer-border:#f4a560,footer-label:#ffa07a,footer:#ffa07a' "
)

WATCH_ARGS = {
    "debounce": 1000,
    "step": 100,
    "watch_filter": DefaultFilter(ignore_dirs=("__pycache__", "build", ".git", ".hg", ".svn", ".tox", ".venv", ".idea", "node_modules", ".mypy_cache", ".pytest_cache", ".hypothesis", ".ronin", "install", "log"),
                                  ignore_entity_patterns=("\\.py[cod]$", "\\.___jb_...___$", "\\.sw.$", "~$", "^\\.\\#", "^\\.DS_Store$", "^flycheck_", "\\.bck$"))
}

FZF_RELOAD_COMMAND = f"curl -XPOST localhost:{{FZF_PROC_PORT}} -d '{{PREPROCESS_CMD}}+reload(bash {DIAGNOSTICS_CMD_FILE})' "

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def get_tmux_window_id() -> str:
    try:
        window_id = subprocess.check_output(
            ["tmux", "display-message", "-p", "#{window_id}"],
            text=True
        ).strip()
        return window_id
    except subprocess.CalledProcessError:
        raise RuntimeError("Failed to get current tmux window ID. Are you in a tmux session?")

def get_file_content_hash(file: str) -> str:
    h = hashlib.blake2b()
    with open(file, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def watch_thread(window_id: str, free_port: int, stop_event: Event):
    files_state = {}
    tmux_hourglass = f"execute(win_name=$(tmux display-message -t {window_id} -p \"#W\" | cut -d'-' -f1); tmux rename-window -t {window_id} \"${{win_name}}-#[fg=#ffd900]  #[default]\";)"
    fzf_reload_cmd = shlex.split(FZF_RELOAD_COMMAND.format(FZF_PROC_PORT=free_port, PREPROCESS_CMD=tmux_hourglass))

    subprocess.run(fzf_reload_cmd, shell=False, cwd=os.getcwd())
    for changes in watch(os.getcwd(), **WATCH_ARGS):
        if stop_event.is_set():
            break
        changed_files = {el[1] for el in changes}
        rerun_diagnostics = False
        for file in changed_files:
            file_hash = get_file_content_hash(file)
            if file not in files_state:
                rerun_diagnostics = True
            elif file_hash != files_state[file]:
                rerun_diagnostics = True
            files_state[file] = file_hash
        if rerun_diagnostics:
            subprocess.run(fzf_reload_cmd, shell=False, cwd=os.getcwd())

if __name__ == "__main__":
    window_id = get_tmux_window_id()
    if not os.path.exists(DIAGNOSTICS_CMD_FILE):
        raise FileNotFoundError(f"File {DIAGNOSTICS_CMD_FILE} not found")

    free_port = get_free_port()
    fzf_cmd = (
                 FZF_CMD
               + f" --listen {free_port}"
               + " --bind \"ctrl-e:execute-silent(tmux send-keys -t '{up-of}' ':open {1}:{2}:{3}' Enter)\" "
               + "--bind 'load:execute-silent( "
                    f"win_name=$(tmux display-message -t {window_id} -p \"#W\" | cut -d'-' -f1); "
                    " if [ \"${FZF_TOTAL_COUNT}\" -gt 0 ]; then "
                        f"tmux rename-window -t {window_id} \"${{win_name}}-#[fg=#ff4400]  #[default]${{FZF_TOTAL_COUNT}} \"; "
                    " else "
                        f"tmux rename-window -t {window_id} \"${{win_name}}\"; "
                    "fi"
                ")' "
               )
    stop_event = Event()
    t = Thread(target=watch_thread, args=(window_id, free_port, stop_event))

    fzf_proc = subprocess.Popen(fzf_cmd, shell=True, cwd=os.getcwd())
    t.start()
    fzf_proc.wait()

    stop_event.set()
    stop_file = Path(".STOP")
    stop_file.touch()
    t.join()
    stop_file.unlink(missing_ok=True)
