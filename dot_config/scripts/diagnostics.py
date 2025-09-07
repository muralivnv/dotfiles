import subprocess
import os
import sys
from typing import Optional
import socket
from argparse import ArgumentParser

FILE_FILTER_CMD_FILE = ".ronin/file-filter.txt"
DIAGNOSTICS_CMD_FILE = ".ronin/diagnostics.txt"

FZF_CMD = (
    "fzf --border -i --preview 'bat {1} --highlight-line {2}' --preview-window 'right,+{2}+3/3,~3' "
    "--delimiter : --nth 1 --scrollbar '▍' --bind=tab:down,shift-tab:up --smart-case --cycle "
    "--style=full:line --layout=reverse --footer 'Error' --bind 'focus:+bg-transform-footer:echo {4} | fold -s -w 100' "
    "--color 'footer-border:#f4a560,footer-label:#ffa07a,footer:#ffa07a' "
)

WATCH_CMD = f"{{FILE_FILTER_CMD}} | entr -r curl -XPOST localhost:{{FZF_PROC_PORT}} -d 'reload(bash {DIAGNOSTICS_CMD_FILE})' "

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def get_file_filter_cmd() -> Optional[str]:
    filter = None
    if os.path.exists(FILE_FILTER_CMD_FILE):
        with open(FILE_FILTER_CMD_FILE, "r") as infile:
            filter = infile.read().strip()
    return filter

def get_tmux_window_id() -> str:
    try:
        window_id = subprocess.check_output(
            ["tmux", "display-message", "-p", "#{window_id}"],
            text=True
        ).strip()
        return window_id
    except subprocess.CalledProcessError:
        raise RuntimeError("Failed to get current tmux window ID. Are you in a tmux session?")

if __name__ == "__main__":
    args = ArgumentParser(description="Diagnostic list")
    args.add_argument("--watch", action="store_true", dest="watch")
    args.add_argument("--port", type=int, default=None, required=False, dest="port")
    args.add_argument("--open", action="store_true", dest="open")
    cli_args, _ = args.parse_known_args()

    window_id = get_tmux_window_id()

    if not os.path.exists(DIAGNOSTICS_CMD_FILE):
        raise FileNotFoundError(f"File {DIAGNOSTICS_CMD_FILE} not found")

    free_port = cli_args.port
    if free_port is None:
        free_port = get_free_port()
    filter = get_file_filter_cmd()
    if filter is None:
        raise FileNotFoundError(f"file {FILE_FILTER_CMD_FILE} not found")

    fzf_cmd = (
                 FZF_CMD
               + f" --listen {free_port}"
               + " --bind \"ctrl-e:execute-silent(tmux send-keys -t '{up-of}' ':open {1}:{2}:{3}' Enter)\" "
               + f"--query={free_port} "
               + "--bind 'load:execute-silent( "
                    f"win_name=$(tmux display-message -t {window_id} -p \"#W\" | cut -d'-' -f1); "
                    " if [ \"${FZF_TOTAL_COUNT}\" -gt 0 ]; then "
                        f"tmux rename-window -t {window_id} \"${{win_name}}-#[fg=yellow]  #[default]${{FZF_TOTAL_COUNT}} \"; "
                    " else "
                        f"tmux rename-window -t {window_id} \"${{win_name}}\"; "
                    "fi"
                ")' "
               )
    watch_cmd = WATCH_CMD.format(FILE_FILTER_CMD=filter, FZF_PROC_PORT=free_port)

    if cli_args.open:
        fzf_proc = subprocess.Popen(fzf_cmd, shell=True, cwd=os.getcwd())
        fzf_proc.wait()
    elif cli_args.watch:
        watch_proc = subprocess.Popen(watch_cmd, shell=True, cwd=os.getcwd())
        watch_proc.wait()
