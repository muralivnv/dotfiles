#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
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
from pathlib import Path

FILE_FILTER_FILE = Path(".ronin/file-filter.txt")
if not FILE_FILTER_FILE.is_file():
    FILE_FILTER_FILE = Path.home() / ".config/ronin/file-filter.txt"
    if not FILE_FILTER_FILE:
        raise FileNotFoundError("config 'file-filter.txt' not found")

FILE_FILTER_CMD = f"bash {FILE_FILTER_FILE}"

TREESITTER_TAGS_CONFIG_FILE = Path(".ronin/treesitter-tags.txt")
if not TREESITTER_TAGS_CONFIG_FILE.is_file():
    TREESITTER_TAGS_CONFIG_FILE = Path.home() / ".config/ronin/treesitter-tags.txt"
    if not TREESITTER_TAGS_CONFIG_FILE:
        raise FileNotFoundError("config 'treesitter-tags.txt' not found")

LAST_PICKER_STATE_FILE      = ".ronin/last-picker-state.txt"

PREVIEW_CMD    = "--preview 'bat {1} --highlight-line {2}' --preview-window 'right,+{2}+3/3,~3' "
FZF_CMD        = (f"fzf --tmux bottom,40% --ansi --border -i {PREVIEW_CMD} "
                  f"--delimiter '@' --scrollbar '▍' "
                  f"--nth=-1 --bind=tab:down,shift-tab:up --smart-case --cycle "
                  f"--style=full:line --layout=reverse --print-query")

CONTENT_PICKER_CMD = f"{FILE_FILTER_CMD} | xargs gai -f '\\w' -v -d @ --files | {FZF_CMD} --tiebreak=begin"
FILE_PICKER_CMD    = f"{FILE_FILTER_CMD} | gai -r '/(\\S+)/$1@1/' | {FZF_CMD} --nth=1 --tiebreak=pathname"

FILE_SYMBOL_PICKER_CMD     = f"sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --files {{FILE_PLACEHOLDER}} | {FZF_CMD} --with-nth=-1 --query='{{QUERY_PLACEHOLDER}}' "
PROJECT_SYMBOL_PICKER_CMD  = f"{FILE_FILTER_CMD} | xargs sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --files | {FZF_CMD} --query='{{QUERY_PLACEHOLDER}}' "

GOTO_DEFINITION_PICKER_CMD = f"{FILE_FILTER_CMD} | xargs sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --files | gai -f '\\b{{QUERY_PLACEHOLDER}}\\b' | ifne {FZF_CMD} --query='{{QUERY_PLACEHOLDER}}' --select-1 --exit-0 "

SHOW_REFERENCES_PICKER_CMD = f"{FILE_FILTER_CMD} | xargs sakura --config {TREESITTER_TAGS_CONFIG_FILE} --definitions --references --files | gai -f '\\b{{QUERY_PLACEHOLDER}}\\b' | ifne {FZF_CMD} --query='{{QUERY_PLACEHOLDER}}' "

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

def execute(name: str, cmd: str, query: str, *rest) -> None:
    try:
        write_state(name, query, *rest)
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
            open_files_in_editor(file_line_col)
    except Exception:
        traceback.print_exc()

def open_content_picker(query: str = ""):
    cmd = CONTENT_PICKER_CMD + " --query=" + shlex.quote(query)
    execute(open_content_picker.__name__, cmd, query)

def open_file_picker(query: str = ""):
    cmd = FILE_PICKER_CMD + " --query=" + shlex.quote(query)
    execute(open_file_picker.__name__, cmd, query)

def open_symbol_picker(query: str = "", file: str = ""):
    if file == "":
        cmd = PROJECT_SYMBOL_PICKER_CMD.replace("{QUERY_PLACEHOLDER}", shlex.quote(query))
    else:
        cmd = FILE_SYMBOL_PICKER_CMD.replace("{FILE_PLACEHOLDER}", file) \
                                    .replace("{QUERY_PLACEHOLDER}", shlex.quote(query))
    execute(open_symbol_picker.__name__, cmd, query, file)

def goto_definition(symbol: str):
    if not symbol:
        return
    cmd = GOTO_DEFINITION_PICKER_CMD.replace("{QUERY_PLACEHOLDER}", symbol)
    execute(goto_definition.__name__, cmd, symbol)

def show_references(symbol: str):
    if not symbol:
        return
    cmd = SHOW_REFERENCES_PICKER_CMD.replace("{QUERY_PLACEHOLDER}", symbol)
    execute(show_references.__name__, cmd, symbol)

if __name__ == "__main__":
    cli_args = ArgumentParser(description="Code navigation using FZF, Gai and Sakura")
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
        open_symbol_picker(file=args.file)
    elif args.goto_definition:
        goto_definition(args.symbol)
    elif args.show_references:
        show_references(args.symbol)
