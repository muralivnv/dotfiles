#!/usr/bin/env bash
set -euo pipefail

# 1. Create a temporary working directory
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# 2. Download the tmux 3.5a release tarball
TAR_URL="https://github.com/tmux/tmux/releases/download/3.5a/tmux-3.5a.tar.gz"
ARCHIVE="$TMP_DIR/tmux-3.5a.tar.gz"
echo "Downloading tmux 3.5a from $TAR_URL..."
curl -L -o "$ARCHIVE" "$TAR_URL"

# 3. Extract the archive
echo "Extracting to $TMP_DIR..."
tar -xzf "$ARCHIVE" -C "$TMP_DIR"

# 4. Change into the extracted source directory
SRC_DIR=$(find "$TMP_DIR" -maxdepth 1 -type d -name "tmux-3.5a*")
cd "$SRC_DIR"

# 5. Install prerequisite packages (Debian/Ubuntu example)
# Uncomment and adjust as needed:
# sudo apt update
# sudo apt install -y automake autoconf pkg-config libevent-dev libncurses-dev build-essential

# 6. Run the build process
echo "Building tmux..."
./configure
make

# 7. Install (into /usr/local by default; adjust with --prefix if desired)
echo "Installing tmux..."
sudo make install

echo "tmux installed successfully."
