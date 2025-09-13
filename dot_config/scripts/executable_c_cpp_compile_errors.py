#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

import subprocess
import sys
import os
from argparse import ArgumentParser
from typing import List, Dict, Set, Tuple, Optional
import json
from dataclasses import dataclass, field, asdict
from concurrent.futures import as_completed, ThreadPoolExecutor
import hashlib
import shlex

ERRORS_CACHE_FOLDER = ".ronin/c_cpp_errors"
ERRORS_STATE_FILE = os.path.join(ERRORS_CACHE_FOLDER, "state.json")

ContentHash = str
PathHash = str

@dataclass
class CompileCommand:
    file: str
    command: List[str]
    path_hash: PathHash = field(init=False)
    content_hash: ContentHash = field(init=False)

    def __post_init__(self):
        self.path_hash = get_file_hash(self.file)
        self.content_hash = get_file_content_hash(self.file)

@dataclass
class TargetFile:
    header_deps: Set[str]
    content_hash: ContentHash
    path_hash: PathHash

@dataclass
class State:
    targets: Dict[str, TargetFile]
    unique_deps: Dict[str, ContentHash]

    @staticmethod
    def from_dict(data: Dict) -> "State":
        targets = {
            k: TargetFile(**v) for k, v in data.get("targets", {}).items()
        }
        for t in targets.values():
            t.header_deps = set(t.header_deps)
        return State(targets=targets, unique_deps=data.get("unique_deps", {}))

def remove_object_file(cmd: str) -> List[str]:
    parts = shlex.split(cmd)
    if "-o" in parts:
        idx = parts.index("-o")
        parts = parts[:idx] + parts[idx+2:]
    return parts

def get_commands_of_interest(compile_commands_path: str, path_prefix: str, cxx: Optional[str],
                             analysis_flags: List[str]) -> Dict[str, CompileCommand]:
    commands = None
    with open(compile_commands_path, "r", encoding="utf8") as infile:
        commands = json.load(infile)
    out = {}
    for c in commands:
        if os.path.exists(c["file"]) and c["file"].startswith(path_prefix):
            out[c["file"]] = CompileCommand(file=c["file"],
                                            command=remove_object_file(c["command"]))
            out[c["file"]].command.extend(analysis_flags)
            if cxx is not None:
                out[c["file"]].command[0] = cxx
    return out

def get_file_hash(file: str) -> str:
    path_bytes = file.encode()
    h = hashlib.new("sha1")
    h.update(path_bytes)
    return h.hexdigest()

def get_file_content_hash(file: str) -> str:
    h = hashlib.blake2b()
    with open(file, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def read_cache(cmd: CompileCommand) -> List[str]:
    cache_file = os.path.join(ERRORS_CACHE_FOLDER, f"{cmd.path_hash}.errors")
    if not os.path.exists(cache_file):
        return []
    errors = []
    with open(cache_file, "r", encoding="utf8") as infile:
        errors = infile.readlines()
    return errors

def run_cmd(cmd: CompileCommand) -> Set[str]:
    cache_file = os.path.join(ERRORS_CACHE_FOLDER, f"{cmd.path_hash}.errors")
    process = subprocess.Popen(cmd.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _, stderr_data = process.communicate()

    with open(cache_file, "w", encoding="utf8") as outfile:
        if not stderr_data:
            outfile.write("")
            return set()
        try:
            diagnostics = json.loads(stderr_data)
        except json.JSONDecodeError:
            outfile.write("")
            return set()
        diagnostics = diagnostics if isinstance(diagnostics, list) else [diagnostics]
        errors = set()
        for diag in diagnostics:
            if diag.get("kind") != "error": continue
            for loc in diag.get("locations", []):
                caret = loc.get("caret", {})
                file = caret.get("file", "<unknown>")
                line_num = caret.get("line", 0)
                col_num = caret.get("column", 0)
                message = diag.get("message", "").replace("\n", " ")
                error = f"{file}:{line_num}:{col_num}:{message}\n"
                errors.add(error)
        for error in errors:
            outfile.write(error)
        return errors

def get_cmd_deps(existing_deps: Set[str], cmd: "CompileCommand", path_prefix: str) -> Set[str]:
    try:
        process = subprocess.run(cmd.command + ["-MM"], capture_output=True, text=True, check=True)
        output = process.stdout.replace("\\\n", "")
        deps = shlex.split(output)
        filtered_deps = set()
        for d in deps[2:]:
            if d in existing_deps:
                filtered_deps.add(d)
        return filtered_deps
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()

def get_deps(existing_deps: Set[str], cmds: Dict[str, CompileCommand],
             path_prefix: str, executor: ThreadPoolExecutor) -> Tuple[Dict[str, Set[str]], Set[str]]:
    new_unique_deps = set()
    cmd_deps = {}
    futures = {executor.submit(get_cmd_deps, existing_deps, cmd, path_prefix): k for k, cmd in cmds.items()}

    for future in as_completed(futures):
        file = futures[future]
        cmd_deps[file] = future.result()
        new_unique_deps.update(cmd_deps[file])
    return cmd_deps, new_unique_deps

def load_or_initialize_state(ignore_cache: bool = False) -> State:
    if (not ignore_cache) and os.path.exists(ERRORS_STATE_FILE):
        with open(ERRORS_STATE_FILE, "r", encoding="utf8") as infile:
            try:
                return State.from_dict(json.load(infile))
            except json.JSONDecodeError:
                return State(targets={}, unique_deps={})
    else:
        state = State(targets={}, unique_deps={})
        return state

def get_changed_deps(deps: Set[str], state: State) -> Set[str]:
    out = set()
    for d in deps:
        if d in state.unique_deps:
            h = get_file_content_hash(d)
            if h != state.unique_deps[d]:
               out.add(d)
        else:
            out.add(d)
    return out

def split_commands(cmds: Dict[str, CompileCommand], cmd_deps: Dict[str, Set[str]],
                   changed_headers: Set[str], state: State) -> Tuple[Set[str], Set[str]]:
    changed_files = set()
    unchanged_files = set()

    for k, c in cmds.items():
        if k in state.targets:
            if state.targets[k].content_hash != c.content_hash:
                changed_files.add(k)
            else:
                if not changed_headers.isdisjoint(cmd_deps[k]):
                    changed_files.add(k)
                else:
                    unchanged_files.add(k)
        else:
            changed_files.add(k)
    return changed_files, unchanged_files

def get_existing_deps(state: State, path_prefix: str,
                      dep_exts: Tuple[str, ...] = (".h", ".hpp", ".hxx", ".hh"),
                      exclude_dirs: Tuple[str, ...] = ("build")) -> Set[str]:
    current_deps: Set[str] = set()
    for root, dirs, files in os.walk(path_prefix):
        # Modify dirs in-place to skip excluded folders
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]

        for file in files:
            if file.endswith(dep_exts):
                full_path = os.path.join(root, file)
                current_deps.add(os.path.normpath(full_path))
    return current_deps

def new_deps_added(deps: Set[str], state: State) -> bool:
    existing_deps = {k for k in state.unique_deps.keys()}
    return existing_deps != deps

def json_set_to_list(obj):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError

if __name__ == "__main__":
    parser = ArgumentParser(description="Parse compile_commands.json and report compiler errors")
    parser.add_argument("--compile-commands", help="Path to compile_commands.json", type=str, required=True, dest="compile_commands")
    parser.add_argument("--path-prefix", help="Only analyze files that has this path prefix", type=str, required=True, dest="path_prefix")
    parser.add_argument("--cxx", help="Use this C++ compiler instead of default specified in compile_commands.json",
                        type=str, required=False, default=None, dest="cxx")
    parser.add_argument("-j", "--jobs", help="Number threads to use", type=int, required=False, default=4, dest="jobs")
    parser.add_argument("--no-cache", help="Ignore caching and perform analysis from scratch",
                        action="store_true", required=False, dest="no_cache")
    parser.add_argument("--analysis-flags", help="Comma separated analysis flags to use",
                        type=lambda s: s.split(","), required=False, default=["-fsyntax-only", "-fdiagnostics-format=json"],
                        dest="analysis_flags")

    args, _ = parser.parse_known_args()

    if not os.path.exists(args.compile_commands):
        print (f"[ERROR] File {args.compile_commands} do not exist")
        sys.exit(1)
    os.makedirs(ERRORS_CACHE_FOLDER, exist_ok=True)

    executor = ThreadPoolExecutor(max_workers=args.jobs)
    state = load_or_initialize_state(args.no_cache)
    cmds = get_commands_of_interest(args.compile_commands, args.path_prefix, args.cxx, args.analysis_flags)
    deps = get_existing_deps(state, args.path_prefix)
    if new_deps_added(deps, state):
        cmd_deps, unique_deps = get_deps(deps, cmds, args.path_prefix, executor)
    else:
        cmd_deps = {k: v.header_deps for k, v in state.targets.items()}
        unique_deps = {k for k in state.unique_deps.keys()}
    changed_deps = get_changed_deps(unique_deps, state)
    changed_files, unchanged_files = split_commands(cmds, cmd_deps, changed_deps, state)

    futures = { **{executor.submit(run_cmd, cmds[f]): f for f in changed_files},
                **{executor.submit(read_cache, cmds[f]): f for f in unchanged_files} }

    for future in as_completed(futures):
        file = futures[future]

        if file not in state.targets:
            state.targets[file] = TargetFile(set(), "", "")
        state.targets[file].header_deps = cmd_deps[file]
        state.targets[file].content_hash = cmds[file].content_hash
        state.targets[file].path_hash = cmds[file].path_hash
        try:
            errors = future.result()
            if errors:
                print(''.join(errors).rstrip('\n'))
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
    executor.shutdown()

    if not args.no_cache:
        for c in deps:
            state.unique_deps[c] = get_file_content_hash(c)
        with open(ERRORS_STATE_FILE, "w", encoding="utf8") as outfile:
            state_dict = asdict(state)
            json.dump(state_dict, outfile, indent=2, default=json_set_to_list)
