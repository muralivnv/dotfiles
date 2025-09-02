#!/usr/bin/env bash
set -euo pipefail

VERSION="5.7"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TAR_URL="https://github.com/eradman/entr/archive/refs/tags/$VERSION.tar.gz"
ARCHIVE="$TMP_DIR/entr.tar.gz"
echo "Downloading entr from $TAR_URL..."
curl -L -o "$ARCHIVE" "$TAR_URL"

echo "Extracting to $TMP_DIR..."
tar -xzf "$ARCHIVE" -C "$TMP_DIR"

SRC_DIR=$(find "$TMP_DIR" -maxdepth 1 -type d -name "entr-*")
cd "$SRC_DIR"

echo "Building entr ..."
./configure
make
cp entr ~/.local/bin/
