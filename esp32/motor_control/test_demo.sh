#!/bin/bash
set -e

PORT="${1:-/dev/ttyACM0}"

if ! python3 -c "import serial" &> /dev/null; then
  echo "Installing pyserial..."
  pip install pyserial
fi

echo "Demo loop on $PORT — Ctrl+C to stop"

python3 - "$PORT" <<'EOF'
import serial, time, sys, signal

port = sys.argv[1]
ser = serial.Serial(port, 115200)
time.sleep(2)

def stop(sig, frame):
    print("\nStopping.")
    ser.write(b's')
    ser.close()
    sys.exit(0)

signal.signal(signal.SIGINT, stop)

cycle = [('FORWARD', b'f'), ('STOP', b's'), ('BACKWARD', b'b'), ('STOP', b's')]

while True:
    for label, cmd in cycle:
        print(label)
        ser.write(cmd)
        time.sleep(10)
EOF
