#!/bin/bash
set -e

FQBN="esp32:esp32:adafruit_feather_esp32s3"
SKETCH_DIR="$(dirname "$0")"
ESP32_URL="https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json"

# Install arduino-cli if not present
if ! command -v arduino-cli &> /dev/null; then
  echo "Installing arduino-cli..."
  curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
  sudo mv bin/arduino-cli /usr/local/bin/
fi

# Install ESP32 board support if not present
if ! arduino-cli core list | grep -q "esp32:esp32"; then
  echo "Setting up ESP32 board support..."
  arduino-cli config init --overwrite
  arduino-cli config add board_manager.additional_urls "$ESP32_URL"
  arduino-cli core update-index
  arduino-cli core install esp32:esp32
fi

# Auto-detect port
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
