#!/usr/bin/env bash
set -e

VERSION="1.2.3"
URL="https://github.com/pkgforge-dev/ghostty-appimage/releases/download/v$VERSION/Ghostty-$VERSION-x86_64.AppImage"
TARGET_DIR="$HOME/.local/bin"
APPIMAGE="$TARGET_DIR/ghostty"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/128x128/apps"
DESKTOP_FILE="$DESKTOP_DIR/ghostty.desktop"
ICON_FILE="$HOME/.local/share/chezmoi/.chezmoiscripts/.ghostty_icon_128x128.png"

echo "Downloading Ghostty-$VERSION AppImage..."
mkdir -p "$TARGET_DIR"
curl -L "$URL" -o "$APPIMAGE"
chmod +x "$APPIMAGE"

echo "Installing icon..."
mkdir -p "$ICON_DIR"
cp "$ICON_FILE" "$ICON_DIR/ghostty.png"
echo "Icon installed to $ICON_DIR/ghostty.png"

mkdir -p "$DESKTOP_DIR"

echo "Creating desktop entry..."
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=Ghostty
Exec=$APPIMAGE
Icon=ghostty
StartupWMClass=Ghostty
Terminal=false
Type=Application
Categories=Utility;TerminalEmulator;
StartupNotify=true
EOF

echo "Updating desktop database..."
update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true

echo "Ghostty installed and launcher added."

# Set Ghostty as default terminal via update-alternatives
if command -v update-alternatives >/dev/null 2>&1; then
    echo "Registering Ghostty as an x-terminal-emulator alternative..."
    sudo update-alternatives --install /usr/bin/x-terminal-emulator x-terminal-emulator "$APPIMAGE" 50

    echo "Setting Ghostty as default x-terminal-emulator..."
    sudo update-alternatives --set x-terminal-emulator "$APPIMAGE"
else
    echo "update-alternatives not found. Skipping default terminal setup."
fi

echo "Done. You may need to log out and back in for the app menu to refresh."
