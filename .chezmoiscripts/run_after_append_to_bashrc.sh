#!/usr/bin/env bash
set -euo pipefail

BASHRC="$HOME/.bashrc"
DEVSHELL_PATH="$HOME/.config/devshell"

echo "Building Nix devshell..."
nix build "${DEVSHELL_PATH}#devShells.x86_64-linux.default" --no-link

# Get path and define alias
# Ensure we capture the path cleanly
GHOSTTY_PATH=$(nix develop "$DEVSHELL_PATH" --command env bash -c "which ghostty")
# Use single quotes for the alias value to prevent issues when sourced later
GHOSTTY_ALIAS="setsid ${GHOSTTY_PATH} >/dev/null 2>\\&1 \\&"

echo "Injecting Nix devshell hooks into .bashrc"

START_MARKER="# --- Nix DevShell Trigger (Must be at end) ---"
END_MARKER="# ---------------------------------------------"

# Remove existing block
sed -i "/${START_MARKER//\//\\/}/,/${END_MARKER//\//\\/}/d" "$BASHRC"

# Use a UNIQUE placeholder that won't collide with normal text
PLACEHOLDER="__INSERT_GHOSTTY_ALIAS_HERE__"

NIX_HOOK=$(cat <<'EOF'
# --- Nix DevShell Trigger (Must be at end) ---
if [ -z "$IN_NIX_SHELL" ]; then
    if [ -z "$BASE_DEVSHELL_SHELL_ACTIVE" ]; then
        export BASE_DEVSHELL_SHELL_ACTIVE=1
        nix develop "/home/murali/.config/devshell"
        unset BASE_DEVSHELL_SHELL_ACTIVE
    fi
else
    source REPLACE_DEVSHELL_PATH/bash_custom_functions.sh
    source REPLACE_DEVSHELL_PATH/fzf-bash-completion.sh
    source REPLACE_DEVSHELL_PATH/bash_config.sh
fi
# Define ghostty alias if not already defined
if ! alias ghostty &>/dev/null; then
    alias ghostty='PLACEHOLDER'
fi
# ---------------------------------------------
EOF
)

# Perform replacements
# 1. Replace Path
NIX_HOOK="${NIX_HOOK//REPLACE_DEVSHELL_PATH/$DEVSHELL_PATH}"
# 2. Replace Alias (using the unique placeholder)
NIX_HOOK="${NIX_HOOK//PLACEHOLDER/$GHOSTTY_ALIAS}"

# Append
if ! grep -qF "nix develop $DEVSHELL_PATH" "$BASHRC"; then
    echo "$NIX_HOOK" >> "$BASHRC"
fi   
