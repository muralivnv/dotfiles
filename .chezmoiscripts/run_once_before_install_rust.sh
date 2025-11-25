#!/usr/bin/env bash
set -euo pipefail

if ! command -v "rustup" > /dev/null; then
  echo "Installing rustup..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
fi
