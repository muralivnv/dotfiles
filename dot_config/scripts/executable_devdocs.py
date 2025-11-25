#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///

import subprocess
import sys
from typing import Optional

WEBPAGES = {
    "DevDocs"     : "https://devdocs.io",
    "tldr.sh"     : "https://tldr.inbrowser.app/",
    "Scipy"       : "https://docs.scipy.org/doc/scipy/search.html",
    "Hacking Cpp" : "https://hackingcpp.com/cpp/cheat_sheets.html"
}

PICKER_CMD = "fzf --ansi --border --bind=tab:down,shift-tab:up " \
             "--cycle --tiebreak=pathname --layout=reverse --style=full:line -e " \
             "--jump-labels=\"iojker\" --bind 'ctrl-j:jump,jump:accept' --bind 'start:jump'"

def create_picker() -> Optional[str]:
    opts = r"\n".join(WEBPAGES.keys())
    try:
        selection = subprocess.check_output(f"echo -e \"{opts}\" | {PICKER_CMD}",
                                            shell=True, universal_newlines=True)
        return WEBPAGES.get(selection.strip())
    except subprocess.CalledProcessError:
        return None
    return None

webpage = create_picker()
if not webpage:
    sys.exit(0)

subprocess.run(f"firefox {webpage}", shell=True)
