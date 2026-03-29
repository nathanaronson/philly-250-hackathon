#!/bin/bash
set -e

echo "Installing dependencies..."
pip install pyserial pynmea2

echo "Disabling serial console and enabling serial hardware..."
sudo raspi-config nonint do_serial_hw 0   # enable serial hardware
sudo raspi-config nonint do_serial_cons 1 # disable login shell over serial

echo "Done. Reboot required for serial changes to take effect."
echo "After reboot, run: python3 gps.py"
read -p "Reboot now? (y/n): " choice
if [ "$choice" = "y" ]; then
  sudo reboot
fi
