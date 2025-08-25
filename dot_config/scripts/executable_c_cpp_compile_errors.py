#!/usr/bin/env python3
import json
import subprocess
import sys
from argparse import ArgumentParser
from typing import List, Optional

COMMAND = (
    "PROJECT={PROJECT_PLACEHOLDER}; "
    "jq -r --arg project \"$PROJECT\" "
    "'map(select(.file | contains($project))) | .[].command | "
    "sub(\" -o [^ ]+\";\"-fsyntax-only -w -fdiagnostics-format=json\")' "
    "{BUILD_DIR_PLACEHOLDER}/compile_commands.json "
    "| xargs -P 4 -I % sh -c '%'"
)

FZF_CMD = (
    "fzf --tmux bottom,40% --border -i --preview 'bat {1} --highlight-line {2}' --preview-window 'right,+{2}+3/3,~3' "
    "--delimiter @ --nth 1 --scrollbar '▍' --bind=tab:down,shift-tab:up --smart-case --cycle "
    "--style=full:line --layout=reverse --footer 'Error' --bind 'focus:+bg-transform-footer:echo {4} | fold -s -w 100' "
    "--color 'footer-border:#f4a560,footer-label:#ffa07a,footer:#ffa07a' "
)

def get_last_active_tmux_pane() -> Optional[str]:
    try:
        pane = subprocess.check_output(
            ["tmux", "display-message", "-p", "#{pane_id}"],
            universal_newlines=True
        ).strip()
        return pane
    except subprocess.CalledProcessError:
        return None

def run(build_dir: str, project: str, interactive: bool = False) -> None:
    cmd = COMMAND.format(PROJECT_PLACEHOLDER=project, BUILD_DIR_PLACEHOLDER=build_dir)
    process = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
    )

    stderr = process.stderr
    if stderr is None:
        print("No stderr stream found — did the command fail to start?", file=sys.stderr)
        return

    fzf_proc = None
    if interactive:
        pane_id = get_last_active_tmux_pane()
        if pane_id is None:
            pane_id = "{up-of}"
        cmd = FZF_CMD + \
            f" --bind \"ctrl-e:execute-silent(tmux send-keys -t '{pane_id}' ':open {{1}}:{{2}}:{{3}}' Enter)\" "
        fzf_proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  shell=True, text=True)

    while True:
        line = stderr.readline()
        if not line:
            # process ended, but wait to ensure it's fully done
            if process.poll() is not None:
                break
            continue

        line = line.strip()
        if not line:
            continue

        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue

        diagnostics = parsed if isinstance(parsed, list) else [parsed]

        for diag in diagnostics:
            if diag.get("kind") != "error":
                continue

            for loc in diag.get("locations", []):
                caret = loc.get("caret") or loc.get("finish") or {}
                file = caret.get("file", "<unknown>")
                line_num = caret.get("line", 0)
                col_num = caret.get("column", 0)
                message = diag.get("message", "").replace("\n", " ")
                formatted = f"{file}@{line_num}@{col_num}@{message}"
                if not interactive:
                    print(formatted, flush=True)
                elif fzf_proc:
                    fzf_proc.stdin.write(formatted + "\n")
                    fzf_proc.stdin.flush()
    process.wait()
    if interactive and fzf_proc:
        fzf_proc.stdin.close()
        fzf_proc.wait()

if __name__ == "__main__":
    parser = ArgumentParser(description="Parse compile_commands.json and report errors")
    parser.add_argument("--build-dir", type=str, required=True, dest="build_dir")
    parser.add_argument("--project", type=str, required=True, dest="project")
    parser.add_argument("--interactive", action="store_true", default=False, dest="interactive")
    args = parser.parse_args()

    run(args.build_dir, args.project, args.interactive)
