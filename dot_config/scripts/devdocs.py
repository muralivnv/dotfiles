#!/usr/bin/python

import subprocess
import webview
import os
import sys
from typing import Optional

WEBPAGES = {
    "DevDocs"     : "https://devdocs.io",
    "tldr.sh"     : "https://tldr.inbrowser.app/",
    "Scipy"       : "https://docs.scipy.org/doc/scipy/search.html",
    "Hacking Cpp" : "https://hackingcpp.com/cpp/cheat_sheets.html"
}

PICKER_CMD = "fzf --ansi --tmux bottom,20%,border-native --border --bind=tab:down,shift-tab:up " \
             "--cycle --tiebreak=pathname --layout=reverse --style=full:line -e " \
             "--jump-labels=\"iojker\" --bind 'ctrl-j:jump,jump:accept' --bind 'start:jump'"
def closed():
    os.kill(os.getpid(), 9)

def create_picker() -> Optional[str]:
    opts = "\\n".join(WEBPAGES.keys())
    try:
        selection = subprocess.check_output(f"echo \"{opts}\" | {PICKER_CMD}",
                                            shell=True, universal_newlines=True)
        return WEBPAGES.get(selection.strip())
    except subprocess.CalledProcessError:
        return None
    return None

webpage = create_picker()
if not webpage:
    sys.exit(0)

home_dir = os.path.expanduser("~")
storage_path = os.path.join(home_dir, ".devdocs_webview_cache")
try:
    window = webview.create_window("Documentation", webpage, frameless=False,
                                   text_select=True, easy_drag=False)
    window.events.closed += closed
    webview.start(storage_path=storage_path, private_mode=False)
except Exception as e:
    print(e)
