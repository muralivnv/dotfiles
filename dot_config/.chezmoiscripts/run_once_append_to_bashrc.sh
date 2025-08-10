#!/usr/bin/env bash
set -euo pipefail

BASHRC="$HOME/.bashrc"

# List all scripts you want to source
FILES=(
  "$HOME/.config/bash_config.sh"
  "$HOME/.config/bash_aliases.sh"
  "$HOME/.config/bash_custom_functions.sh"
)

for file in "${FILES[@]}"; do
  LINE="source \"$file\""
  # Append only if it's not already in .bashrc
  grep -qxF "$LINE" "$BASHRC" || echo "$LINE" >> "$BASHRC"
done
