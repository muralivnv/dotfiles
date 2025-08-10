#!/usr/bin/env bash
set -euo pipefail

VERSION="3.5a"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TAR_URL="https://github.com/tmux/tmux/releases/download/$VERSION/tmux-$VERSION.tar.gz"
ARCHIVE="$TMP_DIR/tmux-$VERSION.tar.gz"
echo "Downloading tmux $VERSION from $TAR_URL..."
curl -L -o "$ARCHIVE" "$TAR_URL"

echo "Extracting to $TMP_DIR..."
tar -xzf "$ARCHIVE" -C "$TMP_DIR"

SRC_DIR=$(find "$TMP_DIR" -maxdepth 1 -type d -name "tmux-$VERSION*")
cd "$SRC_DIR"

echo "Building tmux $VERSION..."
./configure
make

echo "Installing tmux $VERSION..."
sudo make install

echo "tmux $VERSION installed successfully."
