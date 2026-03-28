"""
Simple Raspberry Pi UART receiver for the telemetry radio.

Default behavior:
- opens the Pi hardware UART on /dev/serial0
- listens at 9600 baud, 8N1
- prints clean text messages when newline-terminated ASCII arrives
- prints "Received data" if binary / non-printable bytes arrive

Run on the Pi:
    python radio_receiver.py
"""

from __future__ import annotations

import time

import serial


SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 57600
TIMEOUT_SECONDS = 0.2
MESSAGE_BUFFER_SIZE = 128


def main() -> None:
    rx_buffer = bytearray()
    saw_binary_data = False

    print(f"[rpi] Opening {SERIAL_PORT} at {BAUD_RATE} baud")

    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT_SECONDS) as ser:
        time.sleep(0.25)
        print("[rpi] Listening for radio data")

        while True:
            chunk = ser.read(32)
            if not chunk:
                continue

            for byte in chunk:
                if 32 <= byte <= 126:
                    if saw_binary_data:
                        print("[rpi] Received data")
                        saw_binary_data = False

                    if len(rx_buffer) < MESSAGE_BUFFER_SIZE - 1:
                        rx_buffer.append(byte)
                elif byte in (ord("\r"), ord("\n")):
                    if rx_buffer:
                        print(f"[rpi] Received message: {rx_buffer.decode('ascii', errors='ignore')}")
                        rx_buffer.clear()
                    elif saw_binary_data:
                        print("[rpi] Received data")
                        saw_binary_data = False
                else:
                    if rx_buffer:
                        print(f"[rpi] Received message: {rx_buffer.decode('ascii', errors='ignore')}")
                        rx_buffer.clear()

                    saw_binary_data = True


if __name__ == "__main__":
    main()
