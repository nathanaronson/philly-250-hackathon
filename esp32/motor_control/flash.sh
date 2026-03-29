#!/bin/bash
set -e

FQBN="esp32:esp32:adafruit_feather_esp32s3"
SKETCH_DIR="$(dirname "$0")"
PORT="${1:-$(arduino-cli board list | grep -o '/dev/tty[A-Za-z0-9]*' | head -1)}"

if [ -z "$PORT" ]; then
  echo "Error: No ESP32 found. Is it plugged in?"
  exit 1
fi

echo "Compiling..."
arduino-cli compile --fqbn "$FQBN" "$SKETCH_DIR"

echo "Flashing to $PORT..."
arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"

echo "Done."
