#!/usr/bin/env bash
set -eo pipefail

INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

install_tool() {
  local name=$1
  local target_version=$2
  local version_cmd=$3
  local version_parse_cmd=$4
  local download_url=$5
  local archive_name=$6
  local extracted_bin_path=$7

  local installed_version=""
  if command -v "$name" > /dev/null; then
    installed_version=$($version_cmd 2>&1 | eval "$version_parse_cmd" || echo "")
  fi

  if [[ "$installed_version" != "$target_version" ]]; then
    echo "Installing/updating $name to version $target_version"

    rm -f "$INSTALL_DIR/$name"

    tmpdir=$(mktemp -d)
    archive_path="$tmpdir/$archive_name"

    curl -fsSL "$download_url" -o "$archive_path"

    tar -xzf "$archive_path" -C "$tmpdir"

    mv "$tmpdir/$extracted_bin_path" "$INSTALL_DIR/$name"
    chmod +x "$INSTALL_DIR/$name"
    rm -rf "$tmpdir"
    echo "$name $target_version installed."
  fi
}

# fzf
install_tool "fzf" "0.65.1" \
  "fzf --version" \
  "awk '{print \$1}'" \
  "https://github.com/junegunn/fzf/releases/download/v0.65.1/fzf-0.65.1-linux_amd64.tar.gz" \
  "fzf-0.65.1-linux_amd64.tar.gz" \
  "fzf"

# bat
install_tool "bat" "0.25.0" \
  "bat --version" \
  "awk '{print \$2}'" \
  "https://github.com/sharkdp/bat/releases/download/v0.25.0/bat-v0.25.0-x86_64-unknown-linux-musl.tar.gz" \
  "bat-v0.25.0-x86_64-unknown-linux-musl.tar.gz" \
  "bat-v0.25.0-x86_64-unknown-linux-musl/bat"

# zoxide
install_tool "zoxide" "0.9.8" \
  "zoxide --version" \
  "awk '{print \$2}'" \
  "https://github.com/ajeetdsouza/zoxide/releases/download/v0.9.8/zoxide-0.9.8-x86_64-unknown-linux-musl.tar.gz" \
  "zoxide-0.9.8-x86_64-unknown-linux-musl.tar.gz" \
  "zoxide"

# starship
install_tool "starship" "1.23.0" \
  "starship --version" \
  "head -n1 | awk '{print \$2}'" \
  "https://github.com/starship/starship/releases/download/v1.23.0/starship-x86_64-unknown-linux-musl.tar.gz" \
  "starship-x86_64-unknown-linux-musl.tar.gz" \
  "starship"

# pastel
install_tool "pastel" "0.10.0" \
  "pastel --version" \
  "cut -d' ' -f2" \
  "https://github.com/sharkdp/pastel/releases/download/v0.10.0/pastel-v0.10.0-x86_64-unknown-linux-musl.tar.gz" \
  "pastel-v0.10.0-x86_64-unknown-linux-musl.tar.gz" \
  "pastel-v0.10.0-x86_64-unknown-linux-musl/pastel"

echo "Installing moreutils"
sudo apt install moreutils
