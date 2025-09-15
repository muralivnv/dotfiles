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
from typing import List, TextIO, Tuple, Optional, Callable
from functools import partial
import difflib

type Formatter = Callable[[int, str], None]

BOLD_RED = "\033[1;31m"
BOLD_GREEN = "\033[1;32m"
RESET = "\033[0m"

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
            replacements: List[Tuple[re.Pattern, str]], formatter: Formatter) -> None:
    for k, line in enumerate(stream):
        line = line.rstrip("\n")

        match = None
        if filter and not (match := filter.search(line)):
            continue

        if exclude and exclude.search(line):
            continue

        # replacements
        old_line = None
        for regex, repl in replacements:
            old_line = line
            line = regex.sub(repl, line)
        formatter(k+1, line, match, old_line)

def identity(linenum: int, new_content: str, match: Optional[re.Match], old_content: Optional[str]) -> None:
    _ = linenum
    _ = match
    _ = old_content
    print(new_content)

def diff_print(linenum:int, new_content: str, old_content: str, filename: str, delimiter: str) -> None:
    old_words = old_content.rstrip("\n").split()
    new_words = new_content.rstrip("\n").split()

    diff = list(difflib.ndiff(old_words, new_words))
    if not any(token.startswith(("+", "-")) for token in diff):
        return

    colored_parts = []
    for token in diff:
        if token.startswith("- "):
            colored_parts.append(f"{BOLD_RED}{token[2:]}{RESET}")
        elif token.startswith("+ "):
            colored_parts.append(f"{BOLD_GREEN}{token[2:]}{RESET}")
        elif token.startswith("  "):
            colored_parts.append(token[2:])
    colored_line = " ".join(colored_parts)
    print(f"{filename}{delimiter}{linenum}{delimiter}{colored_line}")

def pretty(linenum:int, new_content: str, match: Optional[re.Match],
           old_content: str, filename: str, delimiter: str) -> None:
    if match:
        line = new_content.rstrip("\n")
        start, end = match.span()
        colored_line = f"{line[:start]}{BOLD_RED}{line[start:end]}{RESET}{line[end:]}"
        print(f"{filename}{delimiter}{linenum}{delimiter}{colored_line}")
    else:
        diff_print(linenum, new_content, old_content, filename, delimiter)

if __name__ == "__main__":
    cli_args = ArgumentParser(description="Modern replacement to Sed and Grep")
    cli_args.add_argument("-f", "--filter", help="regexp to filter (can be specified n-times)",
                          type=str, dest="filters", action="append")

    cli_args.add_argument("-e", "--exclude", help="regexp to exclude (can be specified n-times)",
                          type=str, dest="excludes", action="append")

    cli_args.add_argument("-r", "--replace", help="regexp search and replace (can be specified n-times)",
                          type=str, dest="replacements", action="append")

    cli_args.add_argument("--file", help="input file. If not given, stdin will be used",
                          type=str, default=None, required=False, dest="file")

    cli_args.add_argument("-p", "--pretty", help="pretty print output",
                          action="store_true", required=False, dest="pretty")

    cli_args.add_argument("-d", "--delimiter", help="delimiter to use for pretty print",
                          type=str, required=False, default=":", dest="delimiter")

    cli_args.add_argument("--no-color", action="store_true", required=False, dest="no_color")

    args = cli_args.parse_args()

    formatter = None
    if not args.pretty:
        formatter = identity
    elif args.file is None:
        formatter = partial(pretty, filename="STDIN", delimiter=args.delimiter)
    else:
        formatter = partial(pretty, filename=args.file, delimiter=args.delimiter)

    if args.no_color:
        # set colors to empty
        BOLD_RED = ""
        BOLD_GREEN = ""
        RESET = ""

    try:
        filter = combine_patterns([re.compile(p) for p in (args.filters or [])])
        exclude = combine_patterns([re.compile(p) for p in (args.excludes or [])])
        replacements = [parse_replacement(r) for r in (args.replacements or [])]
    except re.error as e:
        print(f"Error: Invalid regular expression: {e}", file=sys.stderr)
        sys.exit(1)

    if args.file is None:
        process(sys.stdin, filter, exclude, replacements, formatter)
    else:
        if not os.path.exists(args.file):
            raise FileNotFoundError(f"Input file {args.file} does not exist")
        try:
            with open(args.file, "r", encoding="utf8") as f:
                process(f, filter, exclude, replacements, formatter)
        except Exception as e:
            print(f"Error processing {args.file}: {e}", file=sys.stderr)
