#!/usr/bin/env bash
set -euo pipefail

BASHRC="$HOME/.bashrc"
DEVSHELL_PATH="$HOME/.config/devshell"
# Updated: Drops a visible 'profile' symlink right inside your devshell folder
PROFILE_PATH="$DEVSHELL_PATH/profile"

echo "Building and Pinning Nix devshell..."
# Build the shell environment and create a permanent GC root
nix develop "${DEVSHELL_PATH}#devShells.x86_64-linux.default" \
    --profile "$PROFILE_PATH" \
    --command true

# wipe all previous generations of this profile so they don't accumulate
nix-env --profile "$PROFILE_PATH" --delete-generations old

# Capture the path using the cached profile
GHOSTTY_PATH=$(nix develop "$PROFILE_PATH" --command env bash -c "which ghostty")
GHOSTTY_ALIAS="setsid ${GHOSTTY_PATH} >/dev/null 2>\\&1 \\&"

echo "Injecting Nix devshell hooks into .bashrc"

START_MARKER="# --- Nix DevShell Trigger (Must be at end) ---"
END_MARKER="# ---------------------------------------------"

# Remove existing block
sed -i "/${START_MARKER//\//\\/}/,/${END_MARKER//\//\\/}/d" "$BASHRC"

PLACEHOLDER="__INSERT_GHOSTTY_ALIAS_HERE__"

NIX_HOOK=$(cat <<'EOF'
# --- Nix DevShell Trigger (Must be at end) ---
if [ -z "$IN_NIX_SHELL" ]; then
    # Check if interactive, in a pseudo-terminal, AND a display server is running
    if [[ $- == *i* ]] && [[ "$(tty)" == /dev/pts/* ]] && { [ -n "$WAYLAND_DISPLAY" ] || [ -n "$DISPLAY" ]; }; then
        if [ -z "$BASE_DEVSHELL_SHELL_ACTIVE" ]; then
            export BASE_DEVSHELL_SHELL_ACTIVE=1
            # Boot directly from the GC root profile
            nix develop REPLACE_PROFILE_PATH
            unset BASE_DEVSHELL_SHELL_ACTIVE
        fi
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
NIX_HOOK="${NIX_HOOK//REPLACE_DEVSHELL_PATH/$DEVSHELL_PATH}"
NIX_HOOK="${NIX_HOOK//REPLACE_PROFILE_PATH/$PROFILE_PATH}"
NIX_HOOK="${NIX_HOOK//PLACEHOLDER/$GHOSTTY_ALIAS}"

# Append
if ! grep -qF "nix develop $PROFILE_PATH" "$BASHRC"; then
    echo "$NIX_HOOK" >> "$BASHRC"
fi
