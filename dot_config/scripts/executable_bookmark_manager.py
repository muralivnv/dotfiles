#!/usr/bin/python3

# imports
import subprocess
from argparse import ArgumentParser
import os
from typing import List
from time import sleep

# globals
FZF_ERR_CODE_TO_IGNORE = [0, 1, 130]
FZF_CMD = "fzf -m --reverse --color hl:bright-yellow,hl+:bright-red --scrollbar=▌▐ --border=rounded --margin 2%"

# helpers
def parse_link(selection: str) -> List[str]:
    links = []

    lines = selection.split('\n')
    for line in lines:
        line = line.strip()
        if len(line) > 0:
            s = line.find('(')
            e = line.find(')')
            if (s != -1) and (e != -1) and (s < e):
                links.append(line[s+1:e])
    return links

def edit_file(editor: str, bm_filepath: str):
    subprocess.call(f"{editor} {bm_filepath}", shell=True)

def search(bm_filepath: str):
    try:
        selection = subprocess.check_output(f"sed -e '/^$/d' -e '/^\s*#[^()]*$/d' {bm_filepath} | {FZF_CMD}", shell=True)
        selection = selection.decode("utf8")
        links = parse_link(selection)
        if (links is not None) and (any(links)):
            for link in links:
                os.system(f"xdg-open {link}")
                sleep(0.3)

    except subprocess.CalledProcessError as e:
        if e.returncode not in FZF_ERR_CODE_TO_IGNORE:
            print(e)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    args = ArgumentParser()
    args.add_argument("-e", "--edit", action="store_true", dest="enable_edit", required=False)
    args.add_argument("-s", "--search", action="store_true", dest="enable_search", required=False)
    args.add_argument("-E", "--EDITOR", dest="editor", required=False, default="nano", type=str)
    args.add_argument("-f", "--file", type=str, dest="bookmark_file", required=True)

    cli_args = args.parse_args()

    if not os.path.exists(cli_args.bookmark_file):
        print(f"[ERROR] bookmark file does not exist -- {cli_args.bookmark_file}")

    if cli_args.enable_edit:
        edit_file(cli_args.editor, cli_args.bookmark_file)
    elif cli_args.enable_search:
        search(cli_args.bookmark_file)
