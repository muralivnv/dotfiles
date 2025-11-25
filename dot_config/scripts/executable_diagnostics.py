#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = [
#   "watchfiles",
# ]
# ///

import subprocess
from pathlib import Path
import socket
import shlex
import hashlib
from watchfiles import watch, DefaultFilter, Change
from threading import Thread, Event
from argparse import ArgumentParser
import os
import time

DIAGNOSTICS_CMD_FILE = Path(".ronin/diagnostics.txt")

FZF_CMD = (
    "fzf --border -i --preview 'bat {1} --highlight-line {2}' --preview-window 'right,+{2}+3/3,~3' "
    "--delimiter : --nth 1 --scrollbar '▍' --bind=tab:down,shift-tab:up --smart-case --cycle "
    "--style=full:line --layout=reverse --footer 'Error' --bind 'focus:+bg-transform-footer:echo {} | cut -d: -f4- | fold -s -w 100' "
    "--color 'footer-border:#f4a560,footer-label:#ffa07a,footer:#ffa07a' "
)

WATCH_ARGS = {
    "debounce": 1000,
    "step": 100,
    "watch_filter": DefaultFilter(ignore_dirs=("__pycache__", "build", ".git", ".hg", ".svn", ".tox",
                                               ".venv", ".idea", "node_modules", ".mypy_cache", ".pytest_cache",
                                               ".hypothesis", ".ronin", "install", "log"),
                                  ignore_entity_patterns=("\\.py[cod]$", "\\.___jb_...___$", "\\.sw.$", "~$",
                                                          "^\\.\\#", "^\\.DS_Store$", "^flycheck_", "\\.bck$"))
}

FZF_RELOAD_COMMAND = f"curl -XPOST localhost:{{FZF_PROC_PORT}} -d 'reload(bash {DIAGNOSTICS_CMD_FILE})' "

ENV = os.environ.copy()
ENV["PATH"] = f"{Path.home()/'.local/bin'}:{ENV['PATH']}"

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def get_file_content_hash(file: str) -> str:
    h = hashlib.blake2b()
    with open(file, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def watch_thread(free_port: int, stop_event: Event):
    time.sleep(1.0)
    files_state = {}
    fzf_reload_cmd = shlex.split(FZF_RELOAD_COMMAND.format(FZF_PROC_PORT=free_port))
    try:
        subprocess.run(fzf_reload_cmd, shell=False, cwd=Path.cwd(),
                       env=ENV)
    except subprocess.SubprocessError as e:
        print(e)
        exit(1)
    for changes in watch(Path.cwd(), **WATCH_ARGS):
        if stop_event.is_set():
            break
        rerun_diagnostics = False
        for change, file in changes:
            try:
                if change == Change.deleted:
                    continue
                if not Path(file).exists():
                    continue
                file_hash = get_file_content_hash(file)
                if file not in files_state:
                    rerun_diagnostics = True
                elif file_hash != files_state[file]:
                    rerun_diagnostics = True
                files_state[file] = file_hash
            except Exception:
                pass
        if rerun_diagnostics:
            try:
                subprocess.run(fzf_reload_cmd, shell=False, cwd=Path.cwd(),
                               env=ENV)
            except subprocess.SubprocessError as e:
                import traceback
                traceback.print_exc()
                input("Press [Enter] to exit")

if __name__ == "__main__":
    try:
        cli_args = ArgumentParser(description="Interactive diagnostics")
        cli_args.add_argument("--parent-id", type=int, required=True, dest="parent_id")
        args, _ = cli_args.parse_known_args()

        if not DIAGNOSTICS_CMD_FILE.exists():
            raise FileNotFoundError(f"File {DIAGNOSTICS_CMD_FILE} not found")

        free_port = get_free_port()
        fzf_cmd = (
                     FZF_CMD
                   + f" --listen {free_port}"
                   + f" --bind \"ctrl-e:execute-silent(swaymsg '[con_id={args.parent_id}] focus' && wlrctl keyboard type ':open {{1}}:{{2}}:{{3}}')\" "
                   )
        stop_event = Event()
        t = Thread(target=watch_thread, args=(free_port, stop_event))
        fzf_proc = subprocess.Popen(fzf_cmd, shell=True, cwd=Path.cwd(),
                                    env=ENV)
        t.start()
        fzf_proc.wait()

        stop_event.set()
        stop_file = Path(".STOP")
        stop_file.touch()
        t.join()
        stop_file.unlink(missing_ok=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("Press [Enter] to exit")
