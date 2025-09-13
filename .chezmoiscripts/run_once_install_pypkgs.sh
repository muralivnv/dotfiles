#!/usr/bin/env bash
set -euo pipefail

curl -LsSf https://astral.sh/uv/install.sh | sh

uv python install 3.13
