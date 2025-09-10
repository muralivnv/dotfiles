#!/usr/bin/env python3
import sys
import re
from argparse import ArgumentParser
from typing import List, TextIO, Tuple

def parse_replacement(expr: str):
    if len(expr) < 3:
        raise ValueError(f"Invalid replacement: {expr}")
    delim = expr[0]
    parts = expr.split(delim)
    if len(parts) < 3:
        raise ValueError(f"Replacement must be in form {delim}search{delim}replace{delim}")
    _, pattern, replacement, *rest = parts
    return re.compile(pattern), replacement

def process(stream: TextIO, filters: List[re.Pattern], excludes: List[re.Pattern],
            replacements: List[Tuple[re.Pattern, str]], extractors: List[re.Pattern]) -> None:
    for line in stream:
        line = line.rstrip("\n")

        # filters
        if filters and not any(r.search(line) for r in filters):
            continue

        # excludes
        if excludes and any(r.search(line) for r in excludes):
            continue

        # replacements
        for regex, repl in replacements:
            line = regex.sub(repl, line)

        if extractors:
            for regex in extractors:
                m = regex.search(line)
                if m:
                    if m.groups():
                        print("".join(m.groups()))
                    else:
                        print(m.group(0))
            continue
        print(line)

if __name__ == "__main__":
    cli_args = ArgumentParser(description="Modern replacement to Sed and Grep")
    cli_args.add_argument("-f", "--filter", help="regexp to filter",
                          type=str, dest="filters", action="append")

    cli_args.add_argument("-e", "--exclude", help="regexp to exclude",
                          type=str, dest="excludes", action="append")

    cli_args.add_argument("-r", "--replace", help="regexp search and replace",
                          type=str, dest="replacements", action="append")

    cli_args.add_argument("--extract", help="regexp to extract from line",
                          type=str, dest="extractors", action="append")

    cli_args.add_argument("files", nargs="*", help="input files (default: stdin)")

    args = cli_args.parse_args()

    filters      = [re.compile(p) for p in (args.filters or [])]
    excludes     = [re.compile(p) for p in (args.excludes or [])]
    replacements = [parse_replacement(r) for r in (args.replacements or [])]
    extractors   = [re.compile(e) for e in (args.extractors or [])]

    if not args.files:
        process(sys.stdin, filters, excludes, replacements, extractors)
    else:
        for fname in args.files:
            if fname == "-":
                process(sys.stdin, filters, excludes, replacements, extractors)
            else:
                with open(fname, "r", encoding="utf8") as f:
                    process(f, filters, excludes, replacements, extractors)
