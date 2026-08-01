import os
import shlex
import subprocess
import tempfile
import traceback
from pathlib import Path
from typing import List, Optional

from config import (
    DEDUPE_FLIP, FILE_FILTER_CMD, FILE_LIST_CMD, FILE_SYMBOL_PICKER_CMD, HIDE_COLS,
    HIDE_PAD, LAST_PICKER_STATE_FILE, NUM_SYMBOL_ENTRIES, PICKER_CMD,
    SIDEBAR_PANE_FILE, TMUX_POPUP, TMUX_SIDEBAR_WIDTH, TREESITTER_TAGS_CONFIG_FILE,
)
from state import (
    clear_pin, frecency_sorted_files, get_hot_symbols, get_recent_files, load_pins,
    record_co_visit, record_edit, record_symbol_visit, record_visit, set_pin,
    sort_symbol_candidates,
)

# Dimmed colour for the secondary half of a row (file:line behind a symbol).
DIM = "\033[38;5;246m"
RST = "\033[0m"


def payload(row: str) -> str:
    return row.strip().rsplit("\t", 1)[-1]


def to_file_line_col(rows: List[str]) -> List[str]:
    targets = []
    for row in rows:
        fields = payload(row).split("@")
        if len(fields) < 2 or not fields[1].isdigit():
            continue
        col = fields[2] if len(fields) > 2 and fields[2].isdigit() else "0"
        targets.append(f"{fields[0]}:{fields[1]}" + (f":{col}" if col != "0" else ""))
    return targets


def write_state(func: str, *args) -> None:
    LAST_PICKER_STATE_FILE.parent.mkdir(exist_ok=True, parents=True)
    LAST_PICKER_STATE_FILE.write_text(f"{func},{','.join(args)}", encoding="utf-8")


def open_last_picker() -> None:
    if not LAST_PICKER_STATE_FILE.exists():
        return
    data = LAST_PICKER_STATE_FILE.read_text(encoding="utf-8").split(",")
    picker = globals().get(data[0])
    if picker:
        picker(*data[1:])


def get_last_active_tmux_pane() -> Optional[str]:
    override = os.environ.get("NAV_TMUX_PANE")
    if override:
        return override
    try:
        return subprocess.check_output(["tmux", "display-message", "-p", "#{pane_id}"],
                                       text=True).strip()
    except subprocess.CalledProcessError:
        return None


def open_files_in_editor(files: List[str]) -> None:
    target = get_last_active_tmux_pane() or "{up-of}"
    for file in files:
        subprocess.run(f"tmux send-keys -t '{target}' ':open {file}' Enter",
                       shell=True, text=True, check=True)


def run_in_popup(cmd: str, input_data: str | None = None) -> str:
    with tempfile.TemporaryDirectory(prefix="nav.") as tmp:
        selection = Path(tmp) / "selection"
        redirect = f" > {selection}"
        if input_data is not None:
            items = Path(tmp) / "items"
            items.write_text(input_data, encoding="utf-8")
            redirect = f" < {items}" + redirect
        subprocess.run(["bash", "-c", TMUX_POPUP + shlex.quote(cmd + redirect)], check=False)
        return selection.read_text(encoding="utf-8") if selection.exists() else ""


def _run_picker(name: str, cmd: str, query: str, *, state_args: tuple = (),
                input_data: str | None = None, current_file: str = "") -> None:
    try:
        write_state(name, query, *state_args)
        lines = run_in_popup(cmd, input_data).splitlines()
        if not any(lines):
            return
        query, rows = (lines[0], lines[1:]) if len(lines) > 1 else ("", lines[:1])
        write_state(name, query, *state_args)

        targets = to_file_line_col(rows)
        for target in targets:
            parts = target.split(":")
            record_visit(parts[0], parts[1] if len(parts) > 1 else 1,
                         parts[2] if len(parts) > 2 else 0)
        for row in rows:
            fields = payload(row).split("@")
            if len(fields) >= 4:
                record_symbol_visit(fields[3], fields[0], fields[1] if fields[1].isdigit() else 0)
                if current_file:
                    record_co_visit(current_file, fields[0])
        open_files_in_editor(targets)
    except Exception:
        traceback.print_exc()


def _symbol_rows(candidate_cmd: str, current_file: str) -> str:
    candidates = subprocess.run(candidate_cmd, shell=True, capture_output=True,
                                text=True).stdout.strip()
    if not candidates:
        return ""

    rows = sort_symbol_candidates(candidates.splitlines(), current_file)
    parsed = [row.split("@") for row in rows]
    width = max((len(p[3]) for p in parsed if len(p) >= 4), default=0)
    out = []
    for row, fields in zip(rows, parsed):
        if len(fields) < 4:
            out.append(row)
            continue
        symbol, basename = fields[3], os.path.basename(fields[0])
        display = f"{symbol}{' ' * (width - len(symbol) + 2)}{DIM}{basename}:{fields[1]}{RST}"
        out.append(f"{display}{HIDE_PAD}\t{row}")
    return "\n".join(out) + "\n"


def _sakura(*flags: str) -> str:
    """A sakura command over every project file, for the given tag flags."""
    return (f"{FILE_FILTER_CMD} | xargs sakura --config {TREESITTER_TAGS_CONFIG_FILE} "
            f"{' '.join(flags)} --files")


def open_content_picker(query: str = "(?i)") -> None:
    format_awk = (r"""awk -F'@' -v w=""" + str(HIDE_COLS)
                  + r""" '{c="";for(i=3;i<=NF;i++){if(i>3)c=c"@";c=c$i}gsub(/^[[:space:]]+/,"",c);gsub(/[[:space:]]+$/,"",c);n=split($1,a,"/");printf "%s\t\033[38;5;246m%s:%s\033[0m%*s\t%s@%s\n",c,a[n],$2,w,"",$1,$2}'""")
    cmd = (f"{FILE_FILTER_CMD} | xargs gai -f '\\w' -v -d @ --files | {format_awk} | "
           f"{PICKER_CMD} --prompt '[ Search ] ❯ ' --query {shlex.quote(query)}")
    print(cmd)
    _run_picker("open_content_picker", cmd, query)


def open_file_picker(query: str = "(?i)") -> None:
    ranked = frecency_sorted_files()
    cmd = (f"{{ printf '%s\\n' {shlex.quote(ranked)}; {FILE_LIST_CMD}; }} | {DEDUPE_FLIP} | "
           f"{PICKER_CMD} --prompt '[ Files ] ❯ ' --query {shlex.quote(query)}")
    _run_picker("open_file_picker", cmd, query)


def open_symbol_picker(query: str = "(?i)", file: str = "", current_file: str = "") -> None:
    if current_file.startswith("["):
        current_file = ""
    prompt = " --prompt '[ Symbols ] ❯ '"
    if file:
        cmd = (FILE_SYMBOL_PICKER_CMD.replace("{FILE_PLACEHOLDER}", file)
                                     .replace("{QUERY_PLACEHOLDER}", shlex.quote(query)) + prompt)
        _run_picker("open_symbol_picker", cmd, query, state_args=(file,))
        return

    rows = _symbol_rows(_sakura("--definitions"), current_file)
    if rows:
        _run_picker("open_symbol_picker", PICKER_CMD + prompt + f" --query {shlex.quote(query)}",
                    query, state_args=("", current_file), input_data=rows,
                    current_file=current_file)


def goto_definition(symbol: str, current_file: str = "") -> None:
    _symbol_lookup("goto_definition", symbol, current_file, "--definitions",
                   "--select-1 --prompt ' [ Defs ] ❯ '")


def show_references(symbol: str, current_file: str = "") -> None:
    _symbol_lookup("show_references", symbol, current_file, "--definitions --references",
                   "--prompt ' [ Refs ] ❯ '")


def _symbol_lookup(name: str, symbol: str, current_file: str, tags: str, extra: str) -> None:
    if current_file.startswith("["):
        current_file = ""
    if not symbol:
        return
    rows = _symbol_rows(f"{_sakura(tags)} | gai -f '\\b{symbol}\\b'", current_file)
    if rows:
        _run_picker(name, f"{PICKER_CMD} {extra} --query {shlex.quote(symbol)}", symbol,
                    state_args=(current_file,), input_data=rows, current_file=current_file)


def _as_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _open_entry(file: str, line, col) -> None:
    line, col = int(line or 1), int(col or 0)
    record_visit(file, line, col)
    open_files_in_editor([f"{file}:{line}:{col}" if col else f"{file}:{line}"])


def pin_current(slot, current_file: str = "", line=1, col=0) -> None:
    if current_file and not current_file.startswith("[") and _as_int(slot) is not None:
        set_pin(slot, current_file, line, col)


def jump_to_pin(slot) -> None:
    slot = _as_int(slot)
    pins = load_pins()
    if slot is not None and 1 <= slot <= len(pins) and pins[slot - 1]:
        entry = pins[slot - 1]
        _open_entry(entry["file"], entry.get("line", 1), entry.get("col", 0))


def jump_to_trail(index) -> None:
    index = _as_int(index)
    entries = get_recent_files()
    if index is None or not entries:
        return
    pinned = {p["file"] for p in load_pins() if p}
    trail = [e for e in entries[1:] if e[1] not in pinned]
    if 0 <= index < len(trail):
        _, fp, ln, cl = trail[index]
        _open_entry(fp, ln, cl)


def jump_to_symbol(index) -> None:
    index = _as_int(index)
    symbols = get_hot_symbols(NUM_SYMBOL_ENTRIES)
    if index is not None and 0 <= index < len(symbols):
        sym, fp, ln = symbols[index]
        record_symbol_visit(sym, fp, ln)
        _open_entry(fp, ln, 0)


def toggle_sidebar() -> None:
    editor_pane = get_last_active_tmux_pane()
    if not editor_pane:
        return

    if SIDEBAR_PANE_FILE.exists():
        cached = SIDEBAR_PANE_FILE.read_text().strip()
        alive = subprocess.run(["tmux", "list-panes", "-a", "-F", "#{pane_id}"],
                               capture_output=True, text=True).stdout.split()
        SIDEBAR_PANE_FILE.unlink(missing_ok=True)
        if cached in alive:
            subprocess.run(["tmux", "kill-pane", "-t", cached], check=False)
            return

    sidebar = Path(__file__).parent / "sidebar.py"
    result = subprocess.run(
        ["tmux", "split-window", "-h", "-l", str(TMUX_SIDEBAR_WIDTH),
         "-P", "-F", "#{pane_id}", "-t", editor_pane, f"exec uv run --script {sidebar}"],
        capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        SIDEBAR_PANE_FILE.write_text(result.stdout.strip())
        # The sidebar is display-only, so focus goes straight back to the editor.
        subprocess.run(["tmux", "select-pane", "-t", editor_pane], check=False)


HANDLERS = {
    "files":          open_file_picker,
    "content":        open_content_picker,
    "symbols":        open_symbol_picker,
    "goto-def":       goto_definition,
    "show-refs":      show_references,
    "last":           open_last_picker,
    "record-edit":    record_edit,
    "pin":            pin_current,
    "clear-pin":      clear_pin,
    "jump-pin":       jump_to_pin,
    "jump-trail":     jump_to_trail,
    "jump-symbol":    jump_to_symbol,
    "toggle-sidebar": toggle_sidebar,
}


def dispatch(cmd: str, args: List[str]) -> None:
    """Run one command from a flat argument list: positionals, then --key value.

    Unknown commands are ignored rather than raised: the caller is a keybinding,
    and there is nobody to show a traceback to.
    """
    handler = HANDLERS.get(cmd)
    if handler is None:
        return
    positional, keywords, i = [], {}, 0
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            keywords[args[i][2:].replace("-", "_")] = args[i + 1]
            i += 2
        else:
            positional.append(args[i])
            i += 1
    handler(*positional, **keywords)


if __name__ == "__main__":
    import sys
    dispatch(sys.argv[1] if len(sys.argv) > 1 else "", sys.argv[2:])
