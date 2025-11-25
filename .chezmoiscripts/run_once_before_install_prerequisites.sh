#!/usr/bin/env bash
set -euo pipefail

if ! command -v "rustup" > /dev/null; then
  echo "Installing rustup..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
fi

REQUIRED_TOOLS=("meson" "ninja" "tar" "unzip")
MISSING_TOOLS=()
STATUS_CODE=0

echo "--- Checking Required Build Tools ---"
check_tool() {
    local tool_name=$1
    if command -v "$tool_name" >/dev/null 2>&1; then
        echo "✅ $tool_name is installed."
    else
        echo "❌ $tool_name is NOT found."
        MISSING_TOOLS+=("$tool_name")
        STATUS_CODE=1
    fi
}

for tool in "${REQUIRED_TOOLS[@]}"; do
    check_tool "$tool"
done

if [ "$STATUS_CODE" -eq 0 ]; then
    echo "All required tools are present."
else
    echo "⚠️ ERROR: The following tools are missing: ${MISSING_TOOLS[*]}"
    echo "Please install them to proceed with the build process."
fi
echo "-------------------------------------"
exit $STATUS_CODE
