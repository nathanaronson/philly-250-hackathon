#!/usr/bin/env bash
# Run this once on the Raspberry Pi to set up the environment.
# Usage: bash cv/scripts/install_pi.sh  (run from repo root)

set -e

cd "$(dirname "$0")/.."   # run from cv/

echo ">>> Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo ">>> Installing Python dependencies..."
uv sync

echo ""
echo "Done! To run the detector:"
echo "  cd cv && uv run python main.py"
