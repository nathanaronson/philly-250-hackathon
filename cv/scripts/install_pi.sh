#!/usr/bin/env bash
# Run this once on the Raspberry Pi to set up the environment.
# Usage: bash cv/scripts/install_pi.sh  (run from repo root)
#
# NOTE: Uses plain python3 venv instead of uv so that the system-installed
# picamera2 (apt package) is accessible via --system-site-packages.

set -e

cd "$(dirname "$0")/.."   # run from cv/

echo ">>> Installing system dependencies..."
sudo apt update
sudo apt install -y python3-picamera2 python3-venv

echo ">>> Creating venv with access to system packages..."
python3 -m venv --system-site-packages .venv

echo ">>> Installing Python dependencies..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install "opencv-python>=4.9.0"

echo ""
echo "Done! To run the detector:"
echo "  cd cv && .venv/bin/python main.py"
