#!/usr/bin/env bash
set -euo pipefail

VERSION="25.09"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TAR_URL="https://github.com/muralivnv/treesitter_tags/archive/refs/tags/v$VERSION.tar.gz"
ARCHIVE="$TMP_DIR/v$VERSION.tar.gz"
echo "Downloading treesitter_tags $$VERSION from $TAR_URL..."
curl -L -o "$ARCHIVE" "$TAR_URL"

echo "Extracting to $TMP_DIR..."
tar -xzf "$ARCHIVE" -C "$TMP_DIR"

SRC_DIR=$(find "$TMP_DIR" -maxdepth 1 -type d -name "treesitter_tags-$VERSION")
cd "$SRC_DIR"

echo "Building treesitter_tags-$VERSION..."
mkdir build
cmake -B build . -DCMAKE_BUILD_TYPE=Release
cmake --build build

echo "Installing treesitter_tags-$VERSION..."
cp build/treesitter_tags $HOME/.local/bin/
echo "treesitter_tags-$VERSION installed successfully."
