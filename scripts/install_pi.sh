#!/usr/bin/env bash
# Run this once on the Raspberry Pi to set up the environment.
# Usage: bash scripts/install_pi.sh

set -e

echo ">>> Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo ">>> Installing system dependency for picamera2..."
sudo apt update
sudo apt install -y python3-picamera2

echo ">>> Installing Python dependencies via uv..."
# --system-site-packages lets the venv see picamera2 (system-installed)
uv sync --extra-index-url https://pypi.org/simple

echo ""
echo "Done! To run the detector:"
echo "  uv run python main.py"
