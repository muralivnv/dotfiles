#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TAR_URL="https://github.com/tmux/tmux/archive/bb4866047a192388a991566ebf6d9cd3d8b8fee5.tar.gz"
ARCHIVE="$TMP_DIR/tmux.tar.gz"
echo "Downloading tmux from $TAR_URL..."
curl -L -o "$ARCHIVE" "$TAR_URL"

echo "Extracting to $TMP_DIR..."
tar -xzf "$ARCHIVE" -C "$TMP_DIR"

SRC_DIR=$(find "$TMP_DIR" -maxdepth 1 -type d -name "tmux-*")
cd "$SRC_DIR"

# patch for non-blocking popup
curl -L https://patch-diff.githubusercontent.com/raw/tmux/tmux/pull/4379.diff -o 4379.diff
git apply 4379.diff

echo "Building tmux ..."
./autogen.sh
./configure
make

echo "Installing tmux..."
sudo make install

echo "tmux installed successfully."
