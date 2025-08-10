#!/usr/bin/env bash
set -euo pipefail

if ! command -v "rustup" > /dev/null; then
  echo "Installing rustup..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
fi

VERSION="25.07.1"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TAR_URL="https://github.com/helix-editor/helix/archive/refs/tags/$VERSION.tar.gz"
ARCHIVE="$TMP_DIR/helix-$VERSION.tar.gz"
echo "Downloading helix $VERSION from $TAR_URL..."
curl -L -o "$ARCHIVE" "$TAR_URL"

echo "Extracting to $TMP_DIR..."
tar -xzf "$ARCHIVE" -C "$TMP_DIR"

SRC_DIR=$(find "$TMP_DIR" -maxdepth 1 -type d -name "helix-$VERSION*")
cd "$SRC_DIR"
echo "Building helix $VERSION..."

BIN_OUT="$HOME/.local"
HELIX_CFG_PATH="$HOME/.config/helix"
RUNTIME_PATH="$HELIX_CFG_PATH"
cargo install --path helix-term --locked --target-dir build --root="$BIN_OUT" --force

cd "$BIN_OUT/bin"
./hx --grammar fetch
./hx --grammar build

cp -r "$SRC_DIR/runtime/" "$RUNTIME_PATH"
rm -rf "$HELIX_CFG_PATH/runtime/grammars/sources"

echo "Helix $VERSION built successfully and installation complete."
