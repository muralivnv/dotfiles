#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

import sys
import re
import os
from argparse import ArgumentParser
from typing import List, TextIO, Tuple, Optional
import tempfile

def parse_replacement(expr: str) -> Tuple[re.Pattern, str]:
    if len(expr) < 3:
        raise ValueError(f"Invalid replacement: {expr}")
    delim = expr[0]
    parts = expr.split(delim)
    if len(parts) < 3:
        raise ValueError(f"Replacement must be in form {delim}search{delim}replace{delim}")
    _, pattern, replacement, *rest = parts
    return re.compile(pattern), replacement

def combine_patterns(patterns: List[re.Pattern]) -> Optional[re.Pattern]:
    if not patterns:
        return None
    combined = "|".join(f"(?:{p.pattern})" for p in patterns)
    return re.compile(combined)

def process(stream: TextIO, filter: Optional[re.Pattern], exclude: Optional[re.Pattern],
            replacements: List[Tuple[re.Pattern, str]],
            out_stream: TextIO = sys.stdout, fname: Optional[str] = None) -> None:
    verbose_print = False
    if (fname is not None) and (filter or exclude):
        verbose_print = True

    for k, line in enumerate(stream):
        line = line.rstrip("\n")

        if filter and not filter.search(line):
            continue

        if exclude and exclude.search(line):
            continue

        # replacements
        for regex, repl in replacements:
            line = regex.sub(repl, line)

        if not verbose_print:
            print(line, file=out_stream)
        else:
            print(f"{fname}:{k}:0:{line}", file=out_stream)

if __name__ == "__main__":
    cli_args = ArgumentParser(description="Modern replacement to Sed and Grep")
    cli_args.add_argument("-f", "--filter", help="regexp to filter (can be specified n-times)",
                          type=str, dest="filters", action="append")

    cli_args.add_argument("-e", "--exclude", help="regexp to exclude (can be specified n-times)",
                          type=str, dest="excludes", action="append")

    cli_args.add_argument("-r", "--replace", help="regexp search and replace (can be specified n-times)",
                          type=str, dest="replacements", action="append")

    cli_args.add_argument("-o", "--overwrite", help="overwrite in-place",
                          action="store_true", dest="overwrite")

    cli_args.add_argument("files", nargs="*", help="input files (default: stdin)")

    args = cli_args.parse_args()
    try:
        filter      = combine_patterns([re.compile(p) for p in (args.filters or [])])
        exclude     = combine_patterns([re.compile(p) for p in (args.excludes or [])])
        replacements = [parse_replacement(r) for r in (args.replacements or [])]
    except re.error as e:
        print(f"Error: Invalid regular expression: {e}", file=sys.stderr)
        sys.exit(1)

    if args.overwrite and not any(replacements):
        print("Error: flag 'overwrite' can be specified only with replacements")
        sys.exit(1)

    if not args.files:
        process(sys.stdin, filter, exclude, replacements)
    else:
        for fname in args.files:
            if fname == "-":
                process(sys.stdin, filter, exclude, replacements)
            elif not args.overwrite:
                try:
                    with open(fname, "r", encoding="utf8") as f:
                        process(f, filter, exclude, replacements, fname=fname)
                except Exception as e:
                    print(f"Error processing {fname}: {e}", file=sys.stderr)
            else:
                tmp_name = None
                try:
                    dir_name = os.path.dirname(fname)
                    with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tmp:
                        tmp_name = tmp.name
                        with open(fname, "r", encoding="utf8") as f:
                            process(f, filter, exclude, replacements, out_stream=tmp)
                    os.replace(tmp_name, fname)
                finally:
                    if tmp_name and os.path.exists(tmp_name):
                        os.remove(tmp_name)
