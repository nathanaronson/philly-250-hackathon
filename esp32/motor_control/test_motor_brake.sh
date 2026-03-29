#!/bin/bash
set -e

PORT="${1:-/dev/ttyACM0}"

if ! python3 -c "import serial" &> /dev/null; then
  echo "Installing pyserial..."
  pip install pyserial
fi

echo "Engaging brake on $PORT..."
python3 - <<EOF
import serial, time
ser = serial.Serial('$PORT', 115200)
time.sleep(2)

print("Braking (resistive force)...")
ser.write(b'r')
time.sleep(30)

print("Stop.")
ser.write(b's')
ser.close()
EOF
