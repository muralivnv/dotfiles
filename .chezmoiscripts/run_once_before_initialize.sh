#!/usr/bin/env bash

# Define the configuration paths
CHEZMOI_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/chezmoi"
CHEZMOI_CONFIG_FILE="$CHEZMOI_CONFIG_DIR/chezmoi.toml"

echo "Checking chezmoi configuration at $CHEZMOI_CONFIG_FILE..."

# Create the directory and file if they do not exist
mkdir -p "$CHEZMOI_CONFIG_DIR"
touch "$CHEZMOI_CONFIG_FILE"

# Ensure the [data] section exists
if ! grep -q '^\[data\]' "$CHEZMOI_CONFIG_FILE"; then
    echo "" >> "$CHEZMOI_CONFIG_FILE"
    echo "[data]" >> "$CHEZMOI_CONFIG_FILE"
fi

# Check for git_repo_list and initialize if missing
if ! grep -q '^git_repo_list' "$CHEZMOI_CONFIG_FILE"; then
    awk '/^\[data\]/ { print; print "git_repo_list = [ \"~/.local/share/chezmoi\" ]"; next }1' "$CHEZMOI_CONFIG_FILE" > "${CHEZMOI_CONFIG_FILE}.tmp" && mv "${CHEZMOI_CONFIG_FILE}.tmp" "$CHEZMOI_CONFIG_FILE"
    echo "Initialized git_repo_list."
fi

# Check for extra_nix_packages and initialize if missing
if ! grep -q '^extra_nix_packages' "$CHEZMOI_CONFIG_FILE"; then
    awk '/^\[data\]/ { print; print "extra_nix_packages = []"; next }1' "$CHEZMOI_CONFIG_FILE" > "${CHEZMOI_CONFIG_FILE}.tmp" && mv "${CHEZMOI_CONFIG_FILE}.tmp" "$CHEZMOI_CONFIG_FILE"
    echo "Initialized extra_nix_packages."
fi

# Check for ghatothkacha_user_ignore and initialize if missing
if ! grep -q '^ghatothkacha_user_ignore' "$CHEZMOI_CONFIG_FILE"; then
    awk '/^\[data\]/ { print; print "ghatothkacha_user_ignore= \"\""; next }1' "$CHEZMOI_CONFIG_FILE" > "${CHEZMOI_CONFIG_FILE}.tmp" && mv "${CHEZMOI_CONFIG_FILE}.tmp" "$CHEZMOI_CONFIG_FILE"
    echo "Initialized ghatothkacha_user_ignore."
fi

if ! grep -q '^ghatothkacha_history_limit' "$CHEZMOI_CONFIG_FILE"; then
    awk '/^\[data\]/ { print; print "ghatothkacha_history_limit=10000"; next }1' "$CHEZMOI_CONFIG_FILE" > "${CHEZMOI_CONFIG_FILE}.tmp" && mv "${CHEZMOI_CONFIG_FILE}.tmp" "$CHEZMOI_CONFIG_FILE"
    echo "Initialized ghatothkacha_history_limit."
fi

echo "chezmoi configuration check complete."
echo ""

# Nix configuration instructions and interactive prompt
echo "========================================================================"
echo " ACTION REQUIRED: Enable Nix Flakes and Unfree Packages"
echo "========================================================================"
echo "Before chezmoi continues, Nix requires the following configurations."
echo "Please follow the instructions for your specific operating system:"
echo ""
echo "▶ FOR NIXOS USERS:"
echo "  Open /etc/nixos/configuration.nix and ensure these lines are present:"
echo "    nix.settings.experimental-features = [ \"nix-command\" \"flakes\" ];"
echo "    nixpkgs.config.allowUnfree = true;"
echo "  Then apply the changes by running: sudo nixos-rebuild switch"
echo ""
echo "▶ FOR STANDALONE NIX USERS (macOS, Ubuntu, Arch, etc.):"
echo "  1. Enable 'nix-command' and 'flakes':"
echo "     Create or edit ~/.config/nix/nix.conf (or /etc/nix/nix.conf) and add:"
echo "     experimental-features = nix-command flakes"
echo "  2. Allow unfree packages:"
echo "     Create or edit ~/.config/nixpkgs/config.nix and add:"
echo "     { allowUnfree = true; }"
echo "========================================================================"
echo ""

# Loop until a valid yes/no response is given
while true; do
    # Note: </dev/tty is required here so read works properly inside chezmoi
    read -p "Have you completed these steps? (y/n): " yn < /dev/tty
    case $yn in
        [Yy]* ) 
            echo "Confirmed. Proceeding with the rest of the dotfiles setup..."
            break
            ;;
        [Nn]* ) 
            echo "Exiting script. Please run 'chezmoi apply' again once you have configured Nix."
            exit 1
            ;;
        * ) 
            echo "Please answer yes (y) or no (n)."
            ;;
    esac
done
