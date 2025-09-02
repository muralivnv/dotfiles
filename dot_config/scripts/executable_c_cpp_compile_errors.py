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
    "sub(\" -o [^ ]+\";\" -fsyntax-only -w -fdiagnostics-format=json\")' "
    "{BUILD_DIR_PLACEHOLDER}/compile_commands.json "
    r" | sed 's/(/\\(/g; s/)/\\)/g' | parallel -j4 {{}} "
)

def run(build_dir: str, project: str) -> None:
    cmd = COMMAND.format(PROJECT_PLACEHOLDER=project, BUILD_DIR_PLACEHOLDER=build_dir)
    process = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
    )

    stderr = process.stderr
    if stderr is None:
        print("No stderr stream found — did the command fail to start?", file=sys.stderr)
        return

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
                print(formatted, flush=True)
    process.wait()

if __name__ == "__main__":
    parser = ArgumentParser(description="Parse compile_commands.json and report errors")
    parser.add_argument("--build-dir", type=str, required=True, dest="build_dir")
    parser.add_argument("--project", type=str, required=True, dest="project")
    args = parser.parse_args()

    run(args.build_dir, args.project)
