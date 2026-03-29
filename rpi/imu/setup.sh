#!/bin/bash
set -e

echo "Installing smbus2..."
pip install smbus2

echo "Enabling I2C on Pi..."
sudo raspi-config nonint do_i2c 0

echo "Done. Run with: python3 imu.py"
