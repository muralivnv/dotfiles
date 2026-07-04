#!/usr/bin/env bash
set -euo pipefail

echo "Building Nix devshell..."
nix build $HOME/.config/devshell#devShells.x86_64-linux.default
