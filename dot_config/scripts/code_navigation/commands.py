import os
import re
import shlex
import time
import traceback
import subprocess
from typing import Optional, List
from pathlib import Path

from config import (
    LAST_PICKER_STATE_FILE, FZF_CMD, JUMP_LABELS, JUMP_LABELS_NO_AUTO,
    FILE_PICKER_CMD, FILE_SYMBOL_PICKER_CMD,
    FRECENCY_PICKER_CMD, FILE_FILTER_CMD, TREESITTER_TAGS_CONFIG_FILE,
    SIDEBAR_PANE_FILE, TMUX_SIDEBAR_WIDTH,
)
from frecency import (
    record_visit, record_symbol_visit, record_co_visit,
    _load_frecency, _frecency_score, _sort_symbol_candidates,
    _get_frecency_sorted_file_list, get_recent_files, get_hot_symbols,
)
from config import NUM_SYMBOL_ENTRIES
from pins import load_pins, set_pin, clear_pin

# Compiled once at import time; matches fzf output lines of the form filepath@line[@col[@...]]
_FILE_LINE_COL_PATTERN = re.compile(r"^([^@]+)@(\d+)(?:@(.*))?$")

# Dimmed color for secondary info (file:line in symbol pickers, etc.)
DIM = "\033[38;5;246m"
RST = "\033[0m"

# Set by open_last_picker to auto-trigger jump labels on load during replay
_replay_mode = False


def _jump_flags(auto_load: bool = False) -> str:
    """Return fzf jump-label flags. Auto-triggers on load for file/frecency pickers and replay."""
    return JUMP_LABELS if (auto_load or _replay_mode) else JUMP_LABELS_NO_AUTO


def write_state(func: str, *args) -> None:
    """Persist the last picker invocation so it can be replayed by open_last_picker."""
    if not LAST_PICKER_STATE_FILE.exists():
        LAST_PICKER_STATE_FILE.parent.mkdir(exist_ok=True, parents=True)
    with open(LAST_PICKER_STATE_FILE, "w", encoding="utf-8") as outfile:
        outfile.write(f"{func},{','.join(args)}")


def to_file_line_col(contents: List[str]) -> List[str]:
    """Convert @-delimited fzf output lines to editor-friendly file:line[:col] strings.

    Each input line must be in the form: filepath@linenum[@colnum[@...]]
    Returns file:line or file:line:col strings. Lines that do not match are skipped.
    """
    output = []
    for content in contents:
        match = _FILE_LINE_COL_PATTERN.match(content.strip())
        if not match:
            continue
        filename, linenum, rest_of_string = match.groups()
        colnum = '0'
        if rest_of_string:
            parts = rest_of_string.split('@', 1)
            if parts[0].isdigit():
                colnum = parts[0]
        if colnum != '0':
            output.append(f"{filename}:{linenum}:{colnum}")
        else:
            output.append(f"{filename}:{linenum}")
    return output


def get_last_active_tmux_pane() -> Optional[str]:
    """Return the active tmux pane ID, preferring the daemon-injected NAV_TMUX_PANE override."""
    override = os.environ.get("NAV_TMUX_PANE")
    if override:
        return override
    try:
        pane = subprocess.check_output(
            ["tmux", "display-message", "-p", "#{pane_id}"],
            universal_newlines=True
        ).strip()
        return pane
    except subprocess.CalledProcessError:
        return None


def open_files_in_editor(files: List[str]):
    """Send :open <file> keystrokes to the target tmux pane to open each file in the editor."""
    tmux_target = get_last_active_tmux_pane()
    if tmux_target is None:
        tmux_target = '{up-of}'
    for file in files:
        subprocess.run(f"tmux send-keys -t '{tmux_target}' ':open {file}' Enter",
                       shell=True, universal_newlines=True, check=True)


def open_last_picker():
    """Re-open whichever picker was last used, restoring its previous query and arguments."""
    global _replay_mode
    if LAST_PICKER_STATE_FILE.exists():
        with open(LAST_PICKER_STATE_FILE, "r", encoding="utf-8") as infile:
            data = infile.read().split(",")
            symbols = globals()
            if data[0] in symbols:
                _replay_mode = True
                try:
                    symbols[data[0]](*data[1:])
                finally:
                    _replay_mode = False


def execute(name: str, cmd: str, query: str, *rest, input_data: str | None = None) -> None:
    """Run a shell command, parse fzf --print-query output, and open the selected files.

    Saves picker state before and after selection. The first output line is the fzf
    query; remaining lines are selected items. Records file visits and opens files.
    If input_data is provided, it is piped to the command via stdin (avoids shell arg limits).
    """
    try:
        write_state(name, query, *rest)
        if input_data is not None:
            r = subprocess.run(cmd, shell=True, input=input_data,
                               capture_output=True, text=True)
            if r.returncode != 0:
                return
            result = r.stdout
        else:
            result = subprocess.check_output(cmd, shell=True, universal_newlines=True)
        query_and_files = result.splitlines()
        if any(query_and_files):
            if len(query_and_files) == 1:
                query = ""
                files = query_and_files[0]
            else:
                query = query_and_files[0]
                files = query_and_files[1:]
            write_state(name, query, *rest)
            file_line_col = to_file_line_col(files)
            for flc in file_line_col:
                parts = flc.split(":")
                record_visit(parts[0], int(parts[1]) if len(parts) > 1 else 1, int(parts[2]) if len(parts) > 2 else 0)
            open_files_in_editor(file_line_col)
    except Exception:
        traceback.print_exc()


def _format_symbol_lines(lines: list) -> list:
    """Append ANSI-colored display field: bold symbol + dim file:line, column-aligned."""
    max_sym = 0
    parsed = []
    for line in lines:
        parts = line.split("@")
        if len(parts) >= 4:
            max_sym = max(max_sym, len(parts[3]))
        parsed.append(parts)
    result = []
    for line, parts in zip(lines, parsed):
        if len(parts) >= 4:
            symbol = parts[3]
            basename = os.path.basename(parts[0])
            pad = max_sym - len(symbol) + 2
            display = f"{symbol}{' ' * pad}{DIM}{basename}:{parts[1]}{RST}"
            result.append(f"{line}@{display}")
        else:
            result.append(line)
    return result


def execute_sorted(name: str, candidate_cmd: str, fzf_query: str, current_file: str = "", fzf_extra: str = "", state_args: tuple = ()) -> None:
    """Run a candidate command, sort results by frecency, pipe into fzf, and open selections.

    Unlike execute(), this pre-fetches all candidates, sorts them by symbol/file frecency,
    formats them with aligned ANSI display fields, then pipes the sorted list into fzf.
    Also records symbol visits and co-visits after selection.
    """
    try:
        write_state(name, fzf_query, *state_args)
        candidates = subprocess.check_output(candidate_cmd, shell=True, text=True).strip()
        if not candidates:
            return
        sorted_lines = _sort_symbol_candidates(candidates.splitlines(), current_file)
        formatted = _format_symbol_lines(sorted_lines)
        sorted_input = "\n".join(formatted) + "\n"
        fzf_cmd = (f"{FZF_CMD} --tiebreak=index "
                   f"--with-nth=-1 "
                   f"{_jump_flags()} "
                   f"--query={shlex.quote(fzf_query)} {fzf_extra}")
        result = subprocess.run(fzf_cmd, shell=True, input=sorted_input,
                                capture_output=True, text=True, check=True)
        query_and_files = result.stdout.splitlines()
        if any(query_and_files):
            if len(query_and_files) == 1:
                fzf_query = ""
                files = [query_and_files[0]]
            else:
                fzf_query = query_and_files[0]
                files = query_and_files[1:]
            write_state(name, fzf_query, *state_args)
            file_line_col = to_file_line_col(files)
            for flc in file_line_col:
                parts = flc.split(":")
                record_visit(parts[0], int(parts[1]) if len(parts) > 1 else 1, int(parts[2]) if len(parts) > 2 else 0)
            for f in files:
                sym_parts = f.strip().split("@")
                if len(sym_parts) >= 4:
                    try:
                        sym_line = int(sym_parts[1])
                    except (ValueError, IndexError):
                        sym_line = 0
                    record_symbol_visit(sym_parts[3], sym_parts[0], sym_line)
                    if current_file:
                        record_co_visit(current_file, sym_parts[0])
            open_files_in_editor(file_line_col)
    except subprocess.CalledProcessError:
        pass
    except Exception:
        traceback.print_exc()


def open_content_picker(query: str = ""):
    """Open an fzf picker that searches file contents via gai.

    Output lines are formatted as: filepath@linenum@content\\tbasename:linenum (dim).
    The tab separates the searchable content field from the dim filename display field,
    allowing --nth=1 to restrict search to content only. ctrl-f toggles filename matching.
    """
    format_awk = r"""awk -F'@' '{c="";for(i=3;i<=NF;i++){if(i>3)c=c"@";c=c$i}gsub(/^[[:space:]]+/,"",c);gsub(/[[:space:]]+$/,"",c);n=split($1,a,"/");printf "%s@%s@%s\t\033[38;5;246m%s:%s\033[0m\n",$1,$2,c,a[n],$2}'"""
    toggle = (
        "--bind 'ctrl-f:transform:"
        'echo "$FZF_PROMPT" | grep -q "+files" '
        '&& echo "change-nth(1)+change-border-label( Search )+change-prompt(> )" '
        '|| echo "change-nth(1..)+change-border-label( Search+Files )+change-prompt(+files> )"\''
    )
    cmd = (f"{FILE_FILTER_CMD} | xargs gai -f '\\w' -v -d @ --files | {format_awk} | "
           f"{FZF_CMD} --delimiter '[@\\t]' --nth=1 --with-nth=3.. --tiebreak=begin "
           f"--border-label=' Search ' {toggle} {_jump_flags()} --query={shlex.quote(query)}")
    execute(open_content_picker.__name__, cmd, query)


def open_frecency_picker(query: str = ""):
    """Open an fzf picker showing recently visited files ranked by frecency score."""
    data = _load_frecency()
    now = time.time()
    scored = []
    for filepath, entry in data["files"].items():
        if not Path(filepath).exists():
            continue
        score = _frecency_score(entry, now)
        if score <= 0:
            continue
        line = entry.get("last_line", 1)
        col = entry.get("last_col", 0)
        scored.append((score, filepath, line, col))
    if not scored:
        return
    scored.sort(key=lambda x: x[0], reverse=True)
    fzf_input = "\n".join(f"{fp}@{ln}@{cl}" for _, fp, ln, cl in scored) + "\n"
    cmd = f"{FRECENCY_PICKER_CMD} --border-label=' Recent ' --query={shlex.quote(query)}"
    execute(open_frecency_picker.__name__, cmd, query, input_data=fzf_input)


def open_file_picker(query: str = ""):
    """Open an fzf picker for project files, with frecency-sorted results at the top."""
    frecency_part = _get_frecency_sorted_file_list()
    fzf_with_tiebreak = FZF_CMD.replace("--print-query", "--print-query --tiebreak=index")
    if frecency_part:
        filter_output = subprocess.run(
            f"{FILE_FILTER_CMD} | gai -r '/(\\S+)/$1@1/'",
            shell=True, capture_output=True, text=True).stdout
        seen = set()
        deduped = []
        for line in (frecency_part + "\n" + filter_output).splitlines():
            key = line.split("@", 1)[0]
            if key and key not in seen:
                seen.add(key)
                deduped.append(line)
        fzf_input = "\n".join(deduped) + "\n"
        cmd = (f"{fzf_with_tiebreak} --nth=1 --with-nth=1 "
               f"--border-label=' Files ' "
               f"{_jump_flags(auto_load=True)} "
               f"--query={shlex.quote(query)}")
        execute(open_file_picker.__name__, cmd, query, input_data=fzf_input)
    else:
        cmd = FILE_PICKER_CMD + f" --with-nth=1 --border-label=' Files ' {_jump_flags(auto_load=True)} --query={shlex.quote(query)}"
        execute(open_file_picker.__name__, cmd, query)


def open_symbol_picker(query: str = "", file: str = "", current_file: str = ""):
    """Open an fzf picker for symbol definitions.

    If file is given, searches only that file's symbols. Otherwise searches all project
    files with results frecency-sorted by symbol visit history and co-visit patterns.
    Sentinel current_file values like '[scratch]' are treated as empty.
    """
    if current_file.startswith("["):
        current_file = ""
    if file == "":
        candidate_cmd = f"{FILE_FILTER_CMD} | xargs sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --files"
        execute_sorted(open_symbol_picker.__name__, candidate_cmd, query, current_file,
                       fzf_extra="--border-label=' Symbols '", state_args=("", current_file))
    else:
        cmd = FILE_SYMBOL_PICKER_CMD.replace("{FILE_PLACEHOLDER}", file) \
                                    .replace("{QUERY_PLACEHOLDER}", shlex.quote(query))
        if _replay_mode:
            cmd += " --bind 'load:jump'"
        cmd += " --border-label=' Symbols '"
        execute(open_symbol_picker.__name__, cmd, query, file)


def goto_definition(symbol: str, current_file: str = ""):
    """Jump to the definition of the given symbol, auto-selecting if the match is unique."""
    if current_file.startswith("["):
        current_file = ""
    if not symbol:
        return
    candidate_cmd = f"{FILE_FILTER_CMD} | xargs sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --files | gai -f '\\b{symbol}\\b'"
    execute_sorted(goto_definition.__name__, candidate_cmd, symbol, current_file,
                   "--select-1 --exit-0 --border-label=' Definition '", state_args=(current_file,))


def show_references(symbol: str, current_file: str = ""):
    """Open an fzf picker listing all definitions and references of the given symbol."""
    if current_file.startswith("["):
        current_file = ""
    if not symbol:
        return
    candidate_cmd = f"{FILE_FILTER_CMD} | xargs sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --references --files | gai -f '\\b{symbol}\\b'"
    execute_sorted(show_references.__name__, candidate_cmd, symbol, current_file,
                   fzf_extra="--border-label=' References '", state_args=(current_file,))


def _open_entry(file: str, line: int, col: int) -> None:
    """Record a visit and send :open to the editor pane."""
    spec = f"{file}:{line}"
    if col:
        spec = f"{spec}:{col}"
    record_visit(file, int(line) if line else 1, int(col) if col else 0)
    open_files_in_editor([spec])


def pin_current(slot, current_file: str = "", line=1, col=0) -> None:
    """Pin the editor's current file+cursor to the given 1-indexed slot.

    Scratch buffers (buffer_name starts with '[') are skipped — there's no
    file path to pin.
    """
    if not current_file or current_file.startswith("["):
        return
    try:
        set_pin(int(slot), current_file, int(line), int(col))
    except (TypeError, ValueError):
        return


def clear_pin_slot(slot) -> None:
    try:
        clear_pin(int(slot))
    except (TypeError, ValueError):
        return


def jump_to_pin(slot) -> None:
    try:
        slot = int(slot)
    except (TypeError, ValueError):
        return
    pins = load_pins()
    if not (1 <= slot <= len(pins)):
        return
    entry = pins[slot - 1]
    if not entry:
        return
    _open_entry(entry["file"], entry.get("line", 1), entry.get("col", 0))


def jump_to_trail(index) -> None:
    """Jump to the Nth most-recently-visited file (0-indexed).

    Filtering must match the sidebar's load_trail_and_current exactly, or
    `space 5` jumps somewhere different from what the sidebar labels as `5`.
    """
    try:
        index = int(index)
    except (TypeError, ValueError):
        return
    entries = get_recent_files()
    if not entries:
        return
    # Drop the current file (top of the list) and any file already in pins —
    # trail is for files not otherwise addressable.
    pinned_files = {p["file"] for p in load_pins() if p}
    trail = [e for e in entries[1:] if e[1] not in pinned_files]
    if not (0 <= index < len(trail)):
        return
    _, fp, ln, cl = trail[index]
    _open_entry(fp, ln, cl)


def jump_to_symbol(index) -> None:
    """Jump to the Nth hottest symbol (0-indexed).

    The sidebar shows the same list under identical labels; both sides call
    get_hot_symbols with NUM_SYMBOL_ENTRIES so the label-to-target mapping
    is guaranteed consistent. Jumping also re-records the visit, reinforcing
    the symbol's rank.
    """
    try:
        index = int(index)
    except (TypeError, ValueError):
        return
    symbols = get_hot_symbols(NUM_SYMBOL_ENTRIES)
    if not (0 <= index < len(symbols)):
        return
    sym, fp, ln = symbols[index]
    record_symbol_visit(sym, fp, ln)
    _open_entry(fp, ln, 0)


def toggle_sidebar() -> None:
    """Open or close the sidebar tmux pane.

    The pane id is cached in .ronin/sidebar.pane; we verify it's still alive via
    `tmux list-panes -a` before treating the sidebar as open (prevents a stale id
    from blocking re-open after `tmux kill-pane`).
    """
    editor_pane = get_last_active_tmux_pane()
    if not editor_pane:
        return

    # Already open? Kill it.
    if SIDEBAR_PANE_FILE.exists():
        cached = SIDEBAR_PANE_FILE.read_text().strip()
        alive = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id}"],
            capture_output=True, text=True,
        ).stdout.split()
        if cached in alive:
            subprocess.run(["tmux", "kill-pane", "-t", cached], check=False)
            try:
                SIDEBAR_PANE_FILE.unlink()
            except OSError:
                pass
            return
        try:
            SIDEBAR_PANE_FILE.unlink()
        except OSError:
            pass

    # Spawn a new sidebar pane to the right of the editor.
    sidebar_script = Path(__file__).parent / "sidebar.py"
    result = subprocess.run(
        ["tmux", "split-window", "-h", "-l", str(TMUX_SIDEBAR_WIDTH),
         "-P", "-F", "#{pane_id}", "-t", editor_pane,
         f"exec uv run --script {sidebar_script}"],
        capture_output=True, text=True,
    )
    new_pane = result.stdout.strip()
    if result.returncode == 0 and new_pane:
        SIDEBAR_PANE_FILE.write_text(new_pane)
        # Return focus to the editor — the sidebar is display-only.
        subprocess.run(["tmux", "select-pane", "-t", editor_pane], check=False)
