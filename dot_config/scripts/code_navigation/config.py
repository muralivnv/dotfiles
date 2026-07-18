from pathlib import Path
import re

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
RONIN_CACHE_DIR = Path.home() / ".cache" / "ronin" / _sanitized_cwd

LAST_PICKER_STATE_FILE = RONIN_CACHE_DIR / "last-picker-state.txt"
FRECENCY_FILE = RONIN_CACHE_DIR / "frecency.json"
PINS_FILE = RONIN_CACHE_DIR / "pins.json"
SIDEBAR_PANE_FILE = RONIN_CACHE_DIR / "sidebar.pane"

NUM_PIN_SLOTS = 4
NUM_TRAIL_ENTRIES = 5
NUM_SYMBOL_ENTRIES = 7
TMUX_SIDEBAR_WIDTH = 42

# fzf base command shared by all pickers; individual pickers append their own --nth/--with-nth
PREVIEW_CMD    = "--preview 'bat {1} --highlight-line {2}' --preview-window 'right,+{2}+3/3,~3' "
FZF_CMD        = (f"fzf --tmux bottom,40% --ansi --border -i {PREVIEW_CMD} "
                  f"--delimiter '@' --scrollbar '\u258d' "
                  f"--nth=-1 --bind=tab:down,shift-tab:up --smart-case --cycle "
                  f"--style=full:line --layout=reverse --print-query")

# Jump-label bindings for quick keyboard navigation
_JUMP_BASE         = """--jump-labels="iojker123456789" --bind 'ctrl-j:jump,jump:accept' """
JUMP_LABELS        = _JUMP_BASE + "--bind 'load:jump' "   # auto-jump on load (file/frecency pickers)
JUMP_LABELS_NO_AUTO = _JUMP_BASE                           # ctrl-j only (symbol/content pickers)

FILE_PICKER_CMD    = f"{FILE_FILTER_CMD} | gai -r '/(\\S+)/$1@1/' | {FZF_CMD} --nth=1 --tiebreak=pathname"

FILE_SYMBOL_PICKER_CMD = f"sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --files {{FILE_PLACEHOLDER}} | {FZF_CMD} --with-nth=-1 {JUMP_LABELS_NO_AUTO} --query='{{QUERY_PLACEHOLDER}}' "

FRECENCY_PICKER_CMD = (f"fzf --tmux bottom,40% --ansi --border -i {PREVIEW_CMD} "
                       f"--delimiter '@' --scrollbar '\u258d' "
                       f"--nth=1 --with-nth=1 --bind=tab:down,shift-tab:up --smart-case --cycle "
                       f"--style=full:line --layout=reverse --print-query "
                       f"""{JUMP_LABELS}""")
