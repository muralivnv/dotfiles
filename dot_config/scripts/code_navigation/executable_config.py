from pathlib import Path
import shlex
import re
import hashlib

# Config file locations: project-local (.ronin/) take precedence over user-global (~/.config/ronin/)
FILE_FILTER_FILE = Path(".ronin/file-filter.txt")
if not FILE_FILTER_FILE.is_file():
    FILE_FILTER_FILE = Path.home() / ".config/ronin/file-filter.txt"
    if not FILE_FILTER_FILE.is_file():
        raise FileNotFoundError("config 'file-filter.txt' not found")

FILE_FILTER_CMD = f"bash {FILE_FILTER_FILE}"

TREESITTER_TAGS_CONFIG_FILE = Path(".ronin/treesitter-tags.txt")
if not TREESITTER_TAGS_CONFIG_FILE.is_file():
    TREESITTER_TAGS_CONFIG_FILE = Path.home() / ".config/ronin/treesitter-tags.txt"
    if not TREESITTER_TAGS_CONFIG_FILE:
        raise FileNotFoundError("config 'treesitter-tags.txt' not found")

_cwd_str = str(Path.cwd())
_sanitized_cwd = re.sub(r'[^a-zA-Z0-9]', '-', _cwd_str)
_sanitized_cwd = re.sub(r'-+', '-', _sanitized_cwd).strip('-')
RONIN_CACHE_DIR = Path.home() / ".local" / "share" / "ronin" / _sanitized_cwd

LAST_PICKER_STATE_FILE = RONIN_CACHE_DIR / "last-picker-state.txt"
SIDEBAR_PANE_FILE = RONIN_CACHE_DIR / "sidebar.pane"

STATE_DB = RONIN_CACHE_DIR / "state.db"

_dir_hash = hashlib.md5(str(RONIN_CACHE_DIR).encode()).hexdigest()[:8]
SOCK_PATH = f"/tmp/nav-{_dir_hash}.sock"
PID_PATH = RONIN_CACHE_DIR / "nav.pid"
LOG_PATH = RONIN_CACHE_DIR / "nav-daemon.log"

PIN_LABELS = "1234"        # Helix `space 1..4`, and `space p N` to set
TRAIL_LABELS = "56789"     # Helix `space 5..9`
SYMBOL_LABELS = "ijklaeo"  # Helix `space i,j,k,l,a,e,o`

NUM_PIN_SLOTS = len(PIN_LABELS)
NUM_TRAIL_ENTRIES = len(TRAIL_LABELS)
NUM_SYMBOL_ENTRIES = len(SYMBOL_LABELS)
TMUX_SIDEBAR_WIDTH = 42

HIDE_COLS = 300
HIDE_PAD = " " * HIDE_COLS

_SPLIT = ("sel={{@SELECTION@}}; p=${sel##*$'\\t'}; "
          'IFS=@ read -r f l c rest <<< "$p"; ')

_PREVIEW_SHELL = _SPLIT + (
    ': "${l:=1}"; '
    'bat --color=always --highlight-line "$l" '
    '--line-range "$(( l > 15 ? l - 15 : 1 )):$(( l + 25 ))" "$f"'
)

PREVIEW_CMD = ("--preview-command " + shlex.quote(_PREVIEW_SHELL)
               + " --preview-dir right --preview-size 55 ")

_QUERY_PROCESS = "--query-process-command " + shlex.quote("gai --no-color -f {{@QUERY@}}")

PICKER_CMD = ("tooey --ansi --print-query " + PREVIEW_CMD + " " + _QUERY_PROCESS)

FILE_LIST_CMD = FILE_FILTER_CMD + " | awk 'NF{print $0 \"@1\"}'"

DEDUPE_FLIP = ("awk -F'@' -v w=" + str(HIDE_COLS)
               + " '!seen[$1]++{printf \"%s%*s\\t%s\\n\", $1, w, \"\", $0}'")

_FLIP_SYMBOLS = ("awk -F'@' -v w=" + str(HIDE_COLS)
                 + " 'NF{printf \"%s%*s\\t%s\\n\", $NF, w, \"\", $0}'")

FILE_SYMBOL_PICKER_CMD = (
    "sakura --config " + str(TREESITTER_TAGS_CONFIG_FILE)
    + " --definitions --files {FILE_PLACEHOLDER} | " + _FLIP_SYMBOLS + " | " + PICKER_CMD
    + " --query {QUERY_PLACEHOLDER} "
)

TMUX_POPUP = 'tmux display-popup -B -x 0 -y 100% -w 100% -h 40% -d "$PWD" -E '
