#!/bin/bash
set -e

PORT="${1:-/dev/ttyACM0}"

if ! python3 -c "import serial" &> /dev/null; then
  echo "Installing pyserial..."
  pip install pyserial
fi

python3 - "$PORT" <<'EOF'
import serial, sys, tty, termios, time

port = sys.argv[1]
ser = serial.Serial(port, 115200)
time.sleep(2)

def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

COMMANDS = {
    'f': ('FORWARD',  b'f'),
    'b': ('BACKWARD', b'b'),
    's': ('STOP',     b's'),
    'q': ('QUIT',     None),
}

print(f"\nMotor CLI — {port}")
print("  f  forward")
print("  b  backward")
print("  s  stop")
print("  q  quit")
print("-" * 20)

state = "STOP"
while True:
    print(f"[{state}] > ", end="", flush=True)
    key = getch()
    if key not in COMMANDS:
        print(f"{key!r} — unknown key")
        continue
    label, cmd = COMMANDS[key]
    if cmd is None:
        ser.write(b's')
        print("quit")
        break
    ser.write(cmd)
    state = label
    print(label)

ser.close()
EOF
