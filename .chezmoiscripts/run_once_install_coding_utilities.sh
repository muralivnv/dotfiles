#!/usr/bin/env bash
set -euo pipefail

VERSION="25.10.1"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TAR_URL="https://github.com/muralivnv/coding_utilities/archive/refs/tags/v$VERSION.tar.gz"
ARCHIVE="$TMP_DIR/v$VERSION.tar.gz"
echo "Downloading coding_utilities $$VERSION from $TAR_URL..."
curl -L -o "$ARCHIVE" "$TAR_URL"

echo "Extracting to $TMP_DIR..."
tar -xzf "$ARCHIVE" -C "$TMP_DIR"

SRC_DIR=$(find "$TMP_DIR" -maxdepth 1 -type d -name "coding_utilities-$VERSION")
cd "$SRC_DIR"

echo "Building coding_utilities-$VERSION..."
mkdir build
cmake -B build . -DCMAKE_BUILD_TYPE=Release
cmake --build build

echo "Installing coding_utilities-$VERSION..."
cp build/sakura/sakura $HOME/.local/bin/
cp build/gai/gai $HOME/.local/bin/
echo "coding_utilities-$VERSION installed successfully."
