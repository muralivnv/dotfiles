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
import hashlib
from watchfiles import watch, DefaultFilter, Change
from threading import Thread, Event

DIAGNOSTICS_CMD_FILE = Path(".ronin/diagnostics.txt")
DIAGNOSTICS_CACHE = Path(".ronin/diagnostics.cache")

RELOAD_KEY = "M-q"

PREVIEW_CMD = (
    "IFS=: read -r f l c rest <<< {{@SELECTION@}}; "
    'bat --color=always --highlight-line "$l" '
    '--line-range "$(( l > 15 ? l - 15 : 1 )):$(( l + 25 ))" "$f"'
)

OPEN_ACTION = (
    "alt-o:Open="
    "IFS=: read -r f l c rest <<< {{@SELECTION@}}; "
    "tmux send-keys -t '{up-of}' \":open $f:$l:$c\" Enter"
)

RELOAD_ACTION = f"alt-r:Reload=bash {DIAGNOSTICS_CMD_FILE} > {DIAGNOSTICS_CACHE}"

PICKER_CMD = [
    "tooey",
    "--ansi",
    "--prompt", "[ Diagnostics ] ❯ ",
    "--query-process-command", f"cat {DIAGNOSTICS_CACHE} | gai --no-color -f " + "{{@QUERY@}}",
    "--preview-command", PREVIEW_CMD,
    "--preview-dir", "right",
    "--preview-size", "55",
    "--reload-command", f"cat {DIAGNOSTICS_CACHE}",
    "--action", OPEN_ACTION,
    "--action", RELOAD_ACTION,
]

WATCH_ARGS = {
    "debounce": 1000,
    "step": 100,
    "watch_filter": DefaultFilter(ignore_dirs=("__pycache__", "build", ".git", ".hg", ".svn", ".tox",
                                               ".venv", ".idea", "node_modules", ".mypy_cache", ".pytest_cache",
                                               ".hypothesis", ".ronin", "install", "log"),
                                  ignore_entity_patterns=("\\.py[cod]$", "\\.___jb_...___$", "\\.sw.$", "~$",
                                                          "^\\.\\#", "^\\.DS_Store$", "^flycheck_", "\\.bck$"))
}


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


def base_window_name(window_id: str) -> str:
    """The window's name without our suffix. Read once: it does not change under us."""
    name = subprocess.check_output(
        ["tmux", "display-message", "-t", window_id, "-p", "#W"], text=True).strip()
    return name.split("-")[0]


def set_window_name(window_id: str, base: str, suffix: str) -> None:
    subprocess.run(["tmux", "rename-window", "-t", window_id, f"{base}{suffix}"], check=False)


def regenerate() -> int:
    out = subprocess.run(["bash", str(DIAGNOSTICS_CMD_FILE)],
                         capture_output=True, text=True).stdout
    DIAGNOSTICS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS_CACHE.write_text(out, encoding="utf-8")
    return sum(1 for ln in out.splitlines() if ln.strip())


def show_count(window_id: str, base: str, count: int) -> None:
    if count > 0:
        set_window_name(window_id, base, f"-#[fg=#ff4400]  #[default]{count} ")
    else:
        set_window_name(window_id, base, "")


def show_working(window_id: str, base: str) -> None:
    set_window_name(window_id, base, "-#[fg=#ffd900]  #[default]")


def push_reload(pane_id: str, picker: subprocess.Popen) -> None:
    if picker.poll() is None:
        subprocess.run(["tmux", "send-keys", "-t", pane_id, RELOAD_KEY], check=False)


def watch_thread(window_id: str, base: str, pane_id: str, picker: subprocess.Popen,
                 stop_event: Event) -> None:
    files_state = {}
    for changes in watch(Path.cwd(), stop_event=stop_event, **WATCH_ARGS):
        rerun_diagnostics = False
        for change, file in changes:
            try:
                if change == Change.deleted:
                    continue
                if not Path(file).exists():
                    continue
                file_hash = get_file_content_hash(file)
                if file not in files_state or file_hash != files_state[file]:
                    rerun_diagnostics = True
                files_state[file] = file_hash
            except Exception:
                pass
        if rerun_diagnostics:
            show_working(window_id, base)
            show_count(window_id, base, regenerate())
            push_reload(pane_id, picker)


if __name__ == "__main__":
    window_id = get_tmux_window_id()
    if not DIAGNOSTICS_CMD_FILE.exists():
        raise FileNotFoundError(f"File {DIAGNOSTICS_CMD_FILE} not found")

    base_name = base_window_name(window_id)
    pane_id = subprocess.check_output(["tmux", "display-message", "-p", "#{pane_id}"],
                                      text=True).strip()

    show_working(window_id, base_name)
    show_count(window_id, base_name, regenerate())

    picker = subprocess.Popen(PICKER_CMD, stdin=subprocess.PIPE, text=True)
    stop_event = Event()
    t = Thread(target=watch_thread,
               args=(window_id, base_name, pane_id, picker, stop_event), daemon=True)
    t.start()

    picker.communicate(input=DIAGNOSTICS_CACHE.read_text(encoding="utf-8"))

    stop_event.set()
    t.join(timeout=2)
    set_window_name(window_id, base_name, "")
