#!/usr/bin/env python3
import subprocess
import sys
import os
from argparse import ArgumentParser
from typing import List, Optional, TextIO, Dict, Any, Set, Tuple
import json
import re
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, as_completed, ThreadPoolExecutor
import hashlib
import shlex

ERRORS_CACHE_FOLDER = ".ronin/c_cpp_errors"
ERRORS_STATE_FILE = os.path.join(ERRORS_CACHE_FOLDER, "state.json")

@dataclass
class CompileCommand:
    file: str
    command: List[str]

def add_syntax_only_checks(cmd: str) -> str:
    return re.sub(r" -o [^ ]+", " -fsyntax-only -w -fdiagnostics-format=json", cmd)

def get_commands_of_interest(compile_commands_path: str, path_prefix: str) -> List[CompileCommand]:
    commands = None
    with open(compile_commands_path, "r", encoding="utf8") as infile:
        commands = json.load(infile)
    out = []
    for c in commands:
        if os.path.exists(c["file"]) and c["file"].startswith(path_prefix):
            out.append(CompileCommand(file=c["file"],
                                      command=shlex.split(add_syntax_only_checks(c["command"]))))
    return out

def get_file_hash(file: str) -> str:
    path_bytes = file.encode()
    h = hashlib.new("sha1")
    h.update(path_bytes)
    return h.hexdigest()

def print_cache(cmd: CompileCommand) -> List[str]:
    file_hash = get_file_hash(cmd.file)
    cache_file = os.path.join(ERRORS_CACHE_FOLDER, f"{file_hash}.errors")
    if not os.path.exists(cache_file):
        return []
    errors = []
    with open(cache_file, "r", encoding="utf8") as infile:
        errors = infile.readlines()
    return errors

def run_cmd(cmd: CompileCommand) -> List[str]:
    file_hash = get_file_hash(cmd.file)
    cache_file = os.path.join(ERRORS_CACHE_FOLDER, f"{file_hash}.errors")
    process = subprocess.Popen(cmd.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _, stderr_data = process.communicate()

    with open(cache_file, "w", encoding="utf8") as outfile:
        if not stderr_data:
            outfile.write("")
            return []
        try:
            diagnostics = json.loads(stderr_data)
        except json.JSONDecodeError:
            outfile.write("")
            return []
        diagnostics = diagnostics if isinstance(diagnostics, list) else [diagnostics]
        errors = []
        for diag in diagnostics:
            if diag.get("kind") != "error": continue
            for loc in diag.get("locations", []):
                caret = loc.get("caret", {})
                file = caret.get("file", "<unknown>")
                if not file or not str(cmd.file).endswith(file): continue
                line_num = caret.get("line", 0)
                col_num = caret.get("column", 0)
                message = diag.get("message", "").replace("\n", " ")
                error = f"{file}@{line_num}@{col_num}@{message}\n"
                outfile.write(error)
                errors.append(error)
        return errors

def get_cmd_dep(cmd: CompileCommand, path_prefix: str) -> List[str]:
    try:
        process = subprocess.run(cmd.command + ["-MM"], capture_output=True, text=True, check=True)
        output = process.stdout.replace("\\\n", "")
        deps = shlex.split(output)
        filtered_deps = []
        for d in deps[2:]:
            if os.path.exists(d) and d.startswith(path_prefix):
                filtered_deps.append(d)
        return filtered_deps
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

def parse_dependencies(cmds: List[CompileCommand], path_prefix: str,
                       executor: ProcessPoolExecutor) -> Tuple[List[List[str]], Set[str]]:
    unique_headers = set()
    cmds_dep = [[] for _ in range(len(cmds))]

    futures = {executor.submit(get_cmd_dep, cmd, path_prefix): cmd for cmd in cmds}
    order = {c.file: i for c, i in zip(cmds, range(len(cmds)))}

    for i, future in enumerate(as_completed(futures)):
        cmd = futures[future]
        idx = order[cmd.file]
        try:
            cmds_dep[idx] = future.result()
            unique_headers.update(cmds_dep[idx])
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
    return cmds_dep, unique_headers

def load_or_initialize_state() -> Dict[str, Any]:
    if os.path.exists(ERRORS_STATE_FILE):
        with open(ERRORS_STATE_FILE, "r", encoding="utf8") as infile:
            return json.load(infile)
    else:
        state = {}
        state["targets"] = {}
        state["deps"] = {}
        return state

def get_changed_header_list(headers: Set[str], state: Dict[str, Any]) -> Set[str]:
    out = []
    for h in headers:
        m_time = str(os.path.getmtime(h))
        if h in state["deps"]:
            if m_time != state["deps"][h]:
               out.append(h)
        else:
            out.append(h)
    return set(out)

def split_commands(cmds: List[CompileCommand], cmds_dep: List[List[str]],
                   changed_headers: Set[str], state: Dict[str, Any]) -> Tuple[List[CompileCommand], List[List[str]],
                                                                              List[CompileCommand], List[List[str]]]:
    changed_cmds       = []
    changed_cmds_dep   = []
    unchanged_cmds     = []
    unchanged_cmds_dep = []

    for i, c in enumerate(cmds):
        key = c.file
        if key in state["targets"]:
            if state["targets"][key]["st_mtime"] != str(os.path.getmtime(c.file)):
                changed_cmds.append(c)
                changed_cmds_dep.append(cmds_dep[i])
            else:
                deps = set(state["targets"][key]["deps"])
                if not changed_headers.isdisjoint(deps):
                    changed_cmds.append(c)
                    changed_cmds_dep.append(cmds_dep[i])
                else:
                    unchanged_cmds.append(c)
                    unchanged_cmds_dep.append(cmds_dep[i])
        else:
            changed_cmds.append(c)
            changed_cmds_dep.append(cmds_dep[i])
    return changed_cmds, changed_cmds_dep, unchanged_cmds, unchanged_cmds_dep

if __name__ == "__main__":
    parser = ArgumentParser(description="Parse compile_commands.json and report compiler errors")
    parser.add_argument("--compile-commands", type=str, required=True, dest="compile_commands")
    parser.add_argument("--path-prefix", type=str, required=True, dest="path_prefix")
    args, _ = parser.parse_known_args()

    if not os.path.exists(args.compile_commands):
        raise FileNotFoundError(f"File {args.compile_commands} do not exist")
    os.makedirs(ERRORS_CACHE_FOLDER, exist_ok=True)

    executor = ProcessPoolExecutor(max_workers=4)

    cmds = get_commands_of_interest(args.compile_commands, args.path_prefix)
    cmds_dep, unique_headers = parse_dependencies(cmds, args.path_prefix, executor)
    state = load_or_initialize_state()
    changed_headers = get_changed_header_list(unique_headers, state)

    changed_cmds, changed_cmds_dep, \
    unchanged_cmds, unchanged_cmds_dep = split_commands(cmds, cmds_dep, changed_headers, state)

    futures = { **{executor.submit(run_cmd, cmd): cmd for cmd in changed_cmds},
                **{executor.submit(print_cache, cmd): cmd for cmd in unchanged_cmds} }
    deps = changed_cmds_dep + unchanged_cmds_dep
    cmd_to_deps = {c.file: d for c, d in zip(changed_cmds + unchanged_cmds, deps)}

    for i, future in enumerate(as_completed(futures)):
        cmd = futures[future]
        cmd_deps = cmd_to_deps[str(cmd.file)]
        key = str(cmd.file)

        state["targets"][key] = {}
        state["targets"][key]["deps"] = cmd_deps
        state["targets"][key]["st_mtime"] = str(os.path.getmtime(cmd.file))
        state["targets"][key]["hash"] = get_file_hash(cmd.file)
        try:
            errors = future.result()
            if errors:
                print(''.join(errors).rstrip('\n'))
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
    executor.shutdown(wait=True)

    state["deps"] = {}
    for h in unique_headers:
        state["deps"][h] = str(os.path.getmtime(h))

    with open(ERRORS_STATE_FILE, "w", encoding="utf8") as outfile:
        json.dump(state, outfile)
