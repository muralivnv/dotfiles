#!/usr/bin/env bash
set -eo pipefail

# Define the tools required for the build process
REQUIRED_TOOLS=("meson" "ninja" "tar" "unzip")
MISSING_TOOLS=()
STATUS_CODE=0

echo "--- Checking Required Build Tools ---"
check_tool() {
    local tool_name=$1
    if command -v "$tool_name" >/dev/null 2>&1; then
        echo "✅ $tool_name is installed."
    else
        echo "❌ $tool_name is NOT found."
        MISSING_TOOLS+=("$tool_name")
        STATUS_CODE=1
    fi
}

for tool in "${REQUIRED_TOOLS[@]}"; do
    check_tool "$tool"
done

if [ "$STATUS_CODE" -eq 0 ]; then
    echo "All required tools are present."
else
    echo "⚠️ ERROR: The following tools are missing: ${MISSING_TOOLS[*]}"
    echo "Please install them to proceed with the build process."
fi
echo "-------------------------------------"

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
  else
    echo "✅ $name is upto date."
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
WLRCTL_VERSION="25.10.2"

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

# wlrctl
WLRCTL_TEMP_DIR=$(mktemp -d)
WLRCTL_URL="https://github.com/muralivnv/coding_utilities/releases/download/v$WLRCTL_VERSION/wlrctl-v$WLRCTL_VERSION.tar.xz"
WLRCTL_FILENAME="wlrctl-v$WLRCTL_VERSION.tar.xz"
WLRCTL_EXTRACTED_DIR="wlrctl-v$WLRCTL_VERSION"

curl -L -o "$WLRCTL_TEMP_DIR/$WLRCTL_FILENAME" "$WLRCTL_URL"
tar -xJvf "$WLRCTL_TEMP_DIR/$WLRCTL_FILENAME" -C "$WLRCTL_TEMP_DIR" 
cd "$WLRCTL_TEMP_DIR"
meson setup --reconfigure --prefix="$HOME/.local" build
ninja -C build install

# moreutils
if command -v apt >/dev/null 2>&1; then
    # Ubuntu / Debian
    if ! dpkg -s moreutils >/dev/null 2>&1; then
        echo "Installing moreutils (APT)"
        sudo apt update
        sudo apt install -y moreutils
    fi

elif command -v pacman >/dev/null 2>&1; then
    # Arch / Manjaro
    if ! pacman -Qi moreutils >/dev/null 2>&1; then
        echo "Installing moreutils (pacman)"
        sudo pacman -Sy --noconfirm moreutils
    fi

else
    echo "Unsupported distro: no apt or pacman found."
    exit 1
fi
