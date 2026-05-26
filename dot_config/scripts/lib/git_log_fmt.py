#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///

"""Read git log --graph output from stdin, extract commit hashes, output HASH@LINE@display.

Replaces `gai -f "\\w" -v -d @` for log formatting.
Filters out graph-only lines (lines without word characters).
"""

import re
import sys

HASH_RE = re.compile(r"[|/\\ ]*\*[^a-f0-9]*([a-f0-9]{4,})")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
WORD_RE = re.compile(r"\w")

line_num = 0
for raw_line in sys.stdin:
    line = raw_line.rstrip("\n")
    clean = ANSI_RE.sub("", line)
    if not WORD_RE.search(clean):
        continue
    line_num += 1
    m = HASH_RE.search(clean)
    commit_hash = m.group(1) if m else ""
    print(f"{commit_hash}@{line_num}@{line}")
