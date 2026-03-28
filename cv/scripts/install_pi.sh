#!/usr/bin/env bash
# Run this once on the Raspberry Pi to set up the environment.
# Usage: bash cv/scripts/install_pi.sh  (run from repo root)

set -e

echo ">>> Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo ">>> Installing system dependency for picamera2..."
sudo apt update
sudo apt install -y python3-picamera2

echo ">>> Creating venv with access to system packages (needed for picamera2)..."
# Use the system Python so uv can see apt-installed packages like picamera2
uv venv --system-site-packages --python /usr/bin/python3

echo ">>> Installing Python dependencies via uv..."
cd cv && uv sync

echo ""
echo "Done! To run the detector:"
echo "  cd cv && uv run python main.py"
