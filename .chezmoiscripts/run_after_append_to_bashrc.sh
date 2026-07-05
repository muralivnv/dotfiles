#!/usr/bin/env bash
set -euo pipefail

BASHRC="$HOME/.bashrc"
DEVSHELL_PATH="$HOME/.config/devshell"

# Define the exact markers
START_MARKER="# --- Nix DevShell Trigger (Must be at end) ---"
END_MARKER="# ---------------------------------------------"

# Remove the existing block precisely
# This deletes from the specific START line to the specific END line
sed -i "/${START_MARKER//\//\\/}/,/${END_MARKER//\//\\/}/d" "$BASHRC"

# Define the block to append
NIX_HOOK=$(cat <<EOF

${START_MARKER}
if [ -z "\$BASE_DEVSHELL_SHELL_ACTIVE" ]; then
    export BASE_DEVSHELL_SHELL_ACTIVE=1
    nix develop "$DEVSHELL_PATH"
    unset BASE_DEVSHELL_SHELL_ACTIVE
fi
${END_MARKER}
EOF
)

# Append ONLY if the signature is missing (prevents duplicates if script runs twice)
if ! grep -qF "nix develop $DEVSHELL_PATH" "$BASHRC"; then
    echo "$NIX_HOOK" >> "$BASHRC"
fi   