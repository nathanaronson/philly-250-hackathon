#!/usr/bin/env bash
# Run this once on the Raspberry Pi to set up the environment.
# Usage: bash cv/scripts/install_pi.sh  (run from repo root)

set -e

cd "$(dirname "$0")/.."   # run from cv/

echo ">>> Installing system dependencies..."
sudo apt update
sudo apt install -y python3-picamera2

echo ">>> Creating venv using system Python with system site-packages..."
# Use the system Python explicitly so picamera2 (apt-installed) is visible
uv venv --system-site-packages --python "$(which python3)"

echo ">>> Installing Python dependencies..."
uv sync

echo ""
echo "Done! To run the detector:"
echo "  cd cv && uv run python main.py"
