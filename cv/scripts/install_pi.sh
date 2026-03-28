#!/usr/bin/env bash
# Run this once on the Raspberry Pi to set up the environment.
# Usage: bash cv/scripts/install_pi.sh  (run from repo root)
#
# On Pi we install everything via apt so all C-extension packages
# (numpy, opencv, picamera2, simplejpeg) share the same compiled binaries.
# uv is only used to create a venv that points at the system packages.

set -e

cd "$(dirname "$0")/.."   # run from cv/

echo ">>> Installing system dependencies..."
sudo apt update
sudo apt install -y python3-picamera2 python3-numpy python3-opencv

echo ">>> Creating venv using system Python with system site-packages..."
uv venv --system-site-packages --python "$(which python3)"

echo ""
echo "Done! To run the detector:"
echo "  cd cv && uv run python main.py"
