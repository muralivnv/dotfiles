#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

# imports
import subprocess
import os
import re
import shlex
from argparse import ArgumentParser
from typing import Optional, List
import traceback

FILE_FILTER_CMD_FILE        = ".ronin/file-filter.txt"
TREESITTER_TAGS_CONFIG_FILE = ".ronin/treesitter-tags.txt"
LAST_PICKER_STATE_FILE      = ".ronin/last-picker-state.txt"

PREVIEW_CMD    = "--preview 'bat {{1}} --highlight-line {{2}}' --preview-window 'right,+{{2}}+3/3,~3' "
FZF_CMD        = (f"fzf --tmux bottom,40% --ansi --border -i {PREVIEW_CMD} "
                  f"--delimiter '@' --scrollbar '▍' "
                  f"--nth=-1 --bind=tab:down,shift-tab:up --smart-case --cycle "
                  f"--style=full:line --layout=reverse --print-query")

CONTENT_PICKER_CMD = f"{{FILE_FILTER_CMD}} | xargs -I % gai -f '.*[a-zA-Z0-9]' -v -d @ --files % | {FZF_CMD} --tiebreak=begin"
FILE_PICKER_CMD    = f"{{FILE_FILTER_CMD}} | xargs -I % echo '%@1' | {FZF_CMD} --nth=1 --tiebreak=pathname"

FILE_SYMBOL_PICKER_CMD     = f"sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --files {{FILE_PLACEHOLDER}} | {FZF_CMD} --with-nth=-1 --query='{{QUERY_PLACEHOLDER}}' "
PROJECT_SYMBOL_PICKER_CMD  = f"{{FILE_FILTER_CMD}} | xargs sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --files | {FZF_CMD} --query='{{QUERY_PLACEHOLDER}}' "

GOTO_DEFINITION_PICKER_CMD = f"{{FILE_FILTER_CMD}} | xargs sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --files | gai -f '\\b{{QUERY_PLACEHOLDER}}\\b' | ifne {FZF_CMD} --query='{{QUERY_PLACEHOLDER}}' --select-1 --exit-0 "

SHOW_REFERENCES_PICKER_CMD = f"{{FILE_FILTER_CMD}} | xargs sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --references --files | gai -f '\\b{{QUERY_PLACEHOLDER}}\\b' | ifne {FZF_CMD} --query='{{QUERY_PLACEHOLDER}}' "

def write_state(func: str, *args) -> None:
    os.makedirs(".ronin", exist_ok=True)
    with open(LAST_PICKER_STATE_FILE, "w", encoding="utf-8") as outfile:
        outfile.write(f"{func},{','.join(args)}")

def to_file_line_col(contents: List[str]) -> List[str]:
    pattern = re.compile(r"^([^@]+)@(\d+)(?:@(.*))?$")
    output = []
    for content in contents:
        match = pattern.match(content.strip())
        if not match:
            continue
        filename, linenum, rest_of_string = match.groups()
        colnum = '0'
        if rest_of_string:
            parts = rest_of_string.split('@', 1)
            if parts[0].isdigit():
                colnum = parts[0]
        output.append(f"{filename}:{linenum}:{colnum}")
    return output

def get_last_active_tmux_pane() -> Optional[str]:
    try:
        pane = subprocess.check_output(
            ["tmux", "display-message", "-p", "#{pane_id}"],
            universal_newlines=True
        ).strip()
        return pane
    except subprocess.CalledProcessError:
        return None

def open_files_in_editor(files: List[str]):
    tmux_target = get_last_active_tmux_pane()
    if tmux_target is None:
        tmux_target = '{up-of}'
    for file in files:
        subprocess.run(f"tmux send-keys -t '{tmux_target}' ':open {file}' Enter",
                       shell=True, universal_newlines=True, check=True)

def open_last_picker():
    if os.path.exists(LAST_PICKER_STATE_FILE):
        with open(LAST_PICKER_STATE_FILE, "r", encoding="utf-8") as infile:
            data = infile.read().split(",")
            symbols = globals()
            if data[0] in symbols:
                symbols[data[0]](*data[1:])

def get_file_filter_cmd() -> Optional[str]:
    filter = None
    if os.path.exists(FILE_FILTER_CMD_FILE):
        with open(FILE_FILTER_CMD_FILE, "r") as infile:
            filter = infile.read().strip()
    return filter

def open_content_picker(query: str = ""):
    filter = get_file_filter_cmd()
    cmd = CONTENT_PICKER_CMD.format(FILE_FILTER_CMD=filter)
    cmd = cmd + " --query=" + shlex.quote(query)
    try:
        write_state(open_content_picker.__name__, query)
        result = subprocess.check_output(cmd, shell=True, universal_newlines=True)
        query_and_files = result.splitlines()
        if any(query_and_files):
            if len(query_and_files) == 1:
                query = ""
                files = query_and_files[0]
            else:
                query = query_and_files[0]
                files = query_and_files[1:]
            write_state(open_content_picker.__name__, query)
            file_line_col = to_file_line_col(files)
            open_files_in_editor(file_line_col)
    except Exception:
        traceback.print_exc()

def open_file_picker(query: str = ""):
    filter = get_file_filter_cmd()
    if filter is None:
        raise FileNotFoundError(f"File {FILE_FILTER_CMD_FILE} do not exist")
    cmd = FILE_PICKER_CMD.format(FILE_FILTER_CMD=filter)
    cmd = cmd + " --query=" + shlex.quote(query)
    try:
        write_state(open_file_picker.__name__, query)
        result = subprocess.check_output(cmd, shell=True, universal_newlines=True)
        query_and_files = result.splitlines()
        if any(query_and_files):
            if len(query_and_files) == 1:
                query = ""
                files = query_and_files[0]
            else:
                query = query_and_files[0]
                files = query_and_files[1:]
            write_state(open_file_picker.__name__, query)
            file_line_col = to_file_line_col(files)
            open_files_in_editor(file_line_col)
    except Exception:
        traceback.print_exc()

def open_symbol_picker(file: str = "", query: str = ""):
    filter = get_file_filter_cmd()
    if filter is None:
        raise FileNotFoundError(f"File {FILE_FILTER_CMD_FILE} do not exist")
    if file == "":
        cmd = PROJECT_SYMBOL_PICKER_CMD.format(FILE_FILTER_CMD=filter, QUERY_PLACEHOLDER=shlex.quote(query))
    else:
        cmd = FILE_SYMBOL_PICKER_CMD.format(FILE_PLACEHOLDER=file, QUERY_PLACEHOLDER=shlex.quote(query))

    try:
        write_state(open_symbol_picker.__name__, file, query)
        selections = subprocess.check_output(cmd, shell=True, universal_newlines=True)
        query_and_files = selections.splitlines()
        if any(query_and_files):
            if len(query_and_files) == 1:
                query = ""
                files = query_and_files[0]
            else:
                query = query_and_files[0]
                files = query_and_files[1:]
            write_state(open_symbol_picker.__name__, file, query)
            file_line_col = to_file_line_col(files)
            open_files_in_editor(file_line_col)
    except Exception:
        traceback.print_exc()

def goto_definition(symbol: str):
    if not symbol:
        return

    filter = get_file_filter_cmd()
    if filter is None:
        raise FileNotFoundError(f"File {FILE_FILTER_CMD_FILE} do not exist")
    cmd = GOTO_DEFINITION_PICKER_CMD.format(FILE_FILTER_CMD=filter, QUERY_PLACEHOLDER=symbol)
    try:
        write_state(goto_definition.__name__, symbol)
        selections = subprocess.check_output(cmd, shell=True, universal_newlines=True)
        query_and_files = selections.splitlines()
        if not any(query_and_files):
            show_references(symbol)
        else:
            if len(query_and_files) == 1:
                query = ""
                files = query_and_files[0]
            else:
                query = query_and_files[0]
                files = query_and_files[1:]
            write_state(goto_definition.__name__, query)
            file_line_col = to_file_line_col(files)
            open_files_in_editor(file_line_col)
    except Exception:
        traceback.print_exc()

def show_references(symbol: str):
    if not symbol:
        return

    filter = get_file_filter_cmd()
    if filter is None:
        raise FileNotFoundError(f"File {FILE_FILTER_CMD_FILE} do not exist")
    cmd = SHOW_REFERENCES_PICKER_CMD.format(FILE_FILTER_CMD=filter, QUERY_PLACEHOLDER=symbol)

    try:
        write_state(show_references.__name__, symbol)
        selections = subprocess.check_output(cmd, shell=True, universal_newlines=True)
        query_and_files = selections.splitlines()
        if any(query_and_files):
            if len(query_and_files) == 1:
                query = ""
                files = query_and_files[0]
            else:
                query = query_and_files[0]
                files = query_and_files[1:]
            write_state(show_references.__name__, query)
            file_line_col = to_file_line_col(files)
            open_files_in_editor(file_line_col)
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    cli_args = ArgumentParser(description="Code navigation using FZF, Jack and Treesitter")
    cli_args.add_argument("--open-last-picker", action="store_true", default=False, dest="open_last_picker")
    cli_args.add_argument("--open-file-picker", action="store_true", default=False, dest="open_file_picker")
    cli_args.add_argument("--open-content-picker", action="store_true", default=False, dest="open_content_picker")
    cli_args.add_argument("--open-symbol-picker", action="store_true", default=False, dest="open_symbol_picker")
    cli_args.add_argument("--file", type=str, default="", dest="file")
    cli_args.add_argument("--goto-definition", action="store_true", default=False, dest="goto_definition")
    cli_args.add_argument("--show-references", action="store_true", default=False, dest="show_references")
    cli_args.add_argument("--symbol", type=str, default="", dest="symbol")

    args, _ = cli_args.parse_known_args()
    if (args.goto_definition or args.show_references) and not args.symbol:
        cli_args.error("--symbol is required when using --goto-definition or --show-references")

    if args.open_last_picker:
        open_last_picker()
    elif args.open_file_picker:
        open_file_picker()
    elif args.open_content_picker:
        open_content_picker()
    elif args.open_symbol_picker:
        open_symbol_picker(args.file)
    elif args.goto_definition:
        goto_definition(args.symbol)
    elif args.show_references:
        show_references(args.symbol)
