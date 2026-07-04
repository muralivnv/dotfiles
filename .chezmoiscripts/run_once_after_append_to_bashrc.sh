#!/usr/bin/env bash
set -euo pipefail

BASHRC="$HOME/.bashrc"
DEVSHELL_PATH="$HOME/.config/devshell"

NIX_HOOK=$(cat <<EOF

# Only drop into the Nix environment if we aren't already in one
if [ -z "\$IN_NIX_SHELL" ]; then
    echo "Entering Nix Toolkit..."
    exec nix develop $DEVSHELL_PATH
fi
EOF
)

UNIQUE_SIGNATURE="exec nix develop $DEVSHELL_PATH"

# Check for the signature, and append the block if it's missing
if ! grep -qF "$UNIQUE_SIGNATURE" "$BASHRC"; then
    echo "$NIX_HOOK" >> "$BASHRC"
else
    echo "Nix devshell hook already present in .bashrc, skipping."
fi