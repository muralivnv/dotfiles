#!/usr/bin/env python3
import subprocess
import sys
import os
from argparse import ArgumentParser
from typing import List, Optional, TextIO
import json
import re
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib

ERRORS_CACHE_FOLDER = ".ronin/cpp_errors"
HEADER_EXTENSIONS = {".h", ".hpp", ".hh", ".hxx"}

@dataclass
class CompileCommand:
    file: Path
    command: str

def add_syntax_only_checks(cmd: str) -> str:
    return re.sub(r" -o [^ ]+", " -fsyntax-only -w -fdiagnostics-format=json", cmd)

def get_commands_of_interest(compile_commands_path: str, path_prefix: str) -> List[CompileCommand]:
    commands = None
    with open(compile_commands_path, "r", encoding="utf8") as infile:
        commands = json.load(infile)
    out = []
    for c in commands:
        if os.path.exists(c["file"]) and c["file"].startswith(path_prefix):
            out.append(CompileCommand(file=Path(c["file"]), command=add_syntax_only_checks(c["command"])))
    return out

def get_file_hash(file: Path) -> str:
    path_bytes = str(file).encode()
    h = hashlib.new("sha1")
    h.update(path_bytes)
    return h.hexdigest()

def get_file_content_hash(file: Path) -> str:
    h = hashlib.new("sha1")
    with file.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def execute_cmd(cmd: CompileCommand, cache_file: str, content_hash: str) -> List[str]:
    errors = []
    process = subprocess.Popen(
        cmd.command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
    )

    stderr = process.stderr
    if stderr is None:
        print("No stderr stream found — did the command fail to start?", file=sys.stderr)
        return

    with open(cache_file, "w", encoding="utf8") as outfile:
        outfile.write(content_hash + "\n")
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
                    formatted = f"{file}@{line_num}@{col_num}@{message}\n"
                    errors.append(formatted)
                    outfile.write(formatted)
        process.wait()
    return errors

def cat(cache_file: str) -> List[str]:
    errors = []
    with open(cache_file, "r", encoding="utf8") as infile:
        errors = infile.readlines()
    return errors[1:]

def process(cmd: CompileCommand, force_run: bool = False) -> List[str]:
    file_hash = get_file_hash(cmd.file)
    cache_file = os.path.join(ERRORS_CACHE_FOLDER, f"{file_hash}.errors")
    file_content_hash = get_file_content_hash(cmd.file)

    run_cmd = force_run
    if (not run_cmd) and os.path.exists(cache_file):
        # check whether file contents have changed since last time
        # first line contains file content hash
        last_content_hash = ""
        with open(cache_file, "r", encoding="utf8") as infile:
            last_content_hash = infile.readline().strip()
        if last_content_hash != file_content_hash:
            run_cmd = True
    else:
        run_cmd = True

    if run_cmd:
        return execute_cmd(cmd, cache_file, file_content_hash)
    else:
        return cat(cache_file)

def update_header_file_mtimes(path_prefix: str) -> bool:
    any_changed = False
    for root, dirs, files in os.walk(path_prefix):
        # modify dirs in-place to skip unwanted directories
        dirs[:] = [
            d for d in dirs
            if not (d.startswith("build") or d.startswith("."))
        ]

        for f in files:
            ext = Path(f).suffix.lower()
            if ext not in HEADER_EXTENSIONS:
                continue

            file_path = Path(root) / f
            cache_file = os.path.join(ERRORS_CACHE_FOLDER, f"{get_file_hash(file_path)}.mtime")

            try:
                mtime = str(file_path.stat().st_mtime)
            except FileNotFoundError:
                any_changed = True
                continue  # skip deleted files

            if not os.path.exists(cache_file):
                # new file
                any_changed = True
                with open(cache_file, "w", encoding="utf8") as cf:
                    cf.write(mtime + "\n")
            else:
                with open(cache_file, "r", encoding="utf8") as cf:
                    cached_mtime = cf.readline().strip()
                if cached_mtime != mtime:
                    any_changed = True
                    with open(cache_file, "w", encoding="utf8") as cf:
                        cf.write(mtime + "\n")
    return any_changed

if __name__ == "__main__":
    parser = ArgumentParser(description="Parse compile_commands.json and report compiler errors")
    parser.add_argument("--compile-commands", type=str, required=True, dest="compile_commands")
    parser.add_argument("--path-prefix", type=str, required=True, dest="path_prefix")
    args, _ = parser.parse_known_args()

    if not os.path.exists(args.compile_commands):
        raise FileNotFoundError(f"File {args.compile_commands} do not exist")

    cmds = get_commands_of_interest(args.compile_commands, args.path_prefix)
    os.makedirs(ERRORS_CACHE_FOLDER, exist_ok=True)
    any_headers_changed = update_header_file_mtimes(args.path_prefix)

    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process, cmd, any_headers_changed): cmd for cmd in cmds}
        for future in as_completed(futures):
            cmd = futures[future]
            try:
                errors = future.result()
                if errors:
                    for e in errors:
                        print(e, end="")
            except Exception as e:
                print(f"[ERROR] {e}", file=sys.stderr)
