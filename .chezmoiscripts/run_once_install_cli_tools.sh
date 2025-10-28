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
  if command -v "$name" >/dev/null 2>&1; then
    installed_version=$($version_cmd 2>&1 | eval "$version_parse_cmd" || echo "")
  fi

  if [[ "$installed_version" != "$target_version" ]]; then
    echo "Installing/updating $name to version $target_version"

    rm -f "$INSTALL_DIR/$name"

    tmpdir=$(mktemp -d)
    archive_path="$tmpdir/$archive_name"

    echo "Downloading $name..."
    curl -fsSL "$download_url" -o "$archive_path"

    echo "Extracting $archive_name..."
    if [[ "$archive_name" == *.zip ]]; then
      unzip -q "$archive_path" -d "$tmpdir"
    else
      tar -xf "$archive_path" -C "$tmpdir"
    fi

    mv "$tmpdir/$extracted_bin_path" "$INSTALL_DIR/$name"
    chmod +x "$INSTALL_DIR/$name"
    rm -rf "$tmpdir"
    echo "$name $target_version installed."
  fi
}

FZF_VERSION="0.66.1"
BAT_VERSION="0.26.0"
ZOXIDE_VERSION="0.9.8"
STARSHIP_VERSION="1.24.0"
PASTEL_VERSION="0.11.0"
YAZI_VERSION="25.5.31"
GAI_VERSION="25.10.2"
SAKURA_VERSION="25.10.2"

install_tool "fzf" "$FZF_VERSION" \
  "fzf --version" \
  "awk '{print \$1}'" \
  "https://github.com/junegunn/fzf/releases/download/v$FZF_VERSION/fzf-$FZF_VERSION-linux_amd64.tar.gz" \
  "fzf-$FZF_VERSION-linux_amd64.tar.gz" \
  "fzf"

install_tool "bat" "$BAT_VERSION" \
  "bat --version" \
  "awk '{print \$2}'" \
  "https://github.com/sharkdp/bat/releases/download/v$BAT_VERSION/bat-v$BAT_VERSION-x86_64-unknown-linux-musl.tar.gz" \
  "bat-v$BAT_VERSION-x86_64-unknown-linux-musl.tar.gz" \
  "bat-v$BAT_VERSION-x86_64-unknown-linux-musl/bat"

install_tool "zoxide" "$ZOXIDE_VERSION" \
  "zoxide --version" \
  "awk '{print \$2}'" \
  "https://github.com/ajeetdsouza/zoxide/releases/download/v$ZOXIDE_VERSION/zoxide-$ZOXIDE_VERSION-x86_64-unknown-linux-musl.tar.gz" \
  "zoxide-$ZOXIDE_VERSION-x86_64-unknown-linux-musl.tar.gz" \
  "zoxide"

install_tool "starship" "$STARSHIP_VERSION" \
  "starship --version" \
  "head -n1 | awk '{print \$2}'" \
  "https://github.com/starship/starship/releases/download/v$STARSHIP_VERSION/starship-x86_64-unknown-linux-musl.tar.gz" \
  "starship-x86_64-unknown-linux-musl.tar.gz" \
  "starship"

install_tool "pastel" "$PASTEL_VERSION" \
  "pastel --version" \
  "cut -d' ' -f2" \
  "https://github.com/sharkdp/pastel/releases/download/v$PASTEL_VERSION/pastel-v$PASTEL_VERSION-x86_64-unknown-linux-musl.tar.gz" \
  "pastel-v$PASTEL_VERSION-x86_64-unknown-linux-musl.tar.gz" \
  "pastel-v$PASTEL_VERSION-x86_64-unknown-linux-musl/pastel"

install_tool "yazi" "$YAZI_VERSION" \
  "yazi --version" \
  "cut -d' ' -f2" \
  "https://github.com/sxyazi/yazi/releases/download/v$YAZI_VERSION/yazi-x86_64-unknown-linux-musl.zip" \
  "yazi-x86_64-unknown-linux-musl.zip" \
  "yazi-x86_64-unknown-linux-musl/yazi"
  
install_tool "gai" "$GAI_VERSION" \
  "gai --version" \
  "awk '{print \$0}'" \
  "https://github.com/muralivnv/coding_utilities/releases/download/v$GAI_VERSION/gai-v$GAI_VERSION-x86_64-unknown-linux-musl.tar.xz" \
  "gai-v$GAI_VERSION-x86_64-unknown-linux-musl.tar.xz" \
  "gai"

install_tool "sakura" "$SAKURA_VERSION" \
  "sakura --version" \
  "awk '{print \$0}'" \
  "https://github.com/muralivnv/coding_utilities/releases/download/v$SAKURA_VERSION/sakura-v$SAKURA_VERSION-x86_64-unknown-linux-musl.tar.xz" \
  "sakura-v$SAKURA_VERSION-x86_64-unknown-linux-musl.tar.xz" \
  "sakura"

# moreutils
if ! dpkg -s moreutils >/dev/null 2>&1; then
  echo "Installing moreutils"
  sudo apt install -y moreutils
fi
