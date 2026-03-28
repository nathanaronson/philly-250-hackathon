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

echo ">>> Creating venv with access to system packages (needed for picamera2)..."
uv venv --system-site-packages

echo ">>> Installing Python dependencies via uv..."
uv sync

echo ""
echo "Done! To run the detector:"
echo "  uv run python main.py"
