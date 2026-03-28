"""
Simple Raspberry Pi UART receiver for the telemetry radio.

Default behavior:
- opens the Pi hardware UART on /dev/serial0
- listens at 57600 baud, 8N1
- prints clean text messages when newline-terminated ASCII arrives
- ignores binary / non-printable noise

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
MIN_MESSAGE_LENGTH = 4


def _looks_like_text_message(data: bytearray) -> bool:
    if len(data) < MIN_MESSAGE_LENGTH:
        return False

    text = data.decode("ascii", errors="ignore").strip()
    if len(text) < MIN_MESSAGE_LENGTH:
        return False

    return any(char.isalpha() for char in text)


def main() -> None:
    rx_buffer = bytearray()

    print(f"[rpi] Opening {SERIAL_PORT} at {BAUD_RATE} baud")

    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT_SECONDS) as ser:
        time.sleep(0.25)
        ser.reset_input_buffer()
        print("[rpi] Listening for radio data")

        while True:
            chunk = ser.read(32)
            if not chunk:
                continue

            for byte in chunk:
                if 32 <= byte <= 126:
                    if len(rx_buffer) < MESSAGE_BUFFER_SIZE - 1:
                        rx_buffer.append(byte)
                elif byte in (ord("\r"), ord("\n")):
                    if _looks_like_text_message(rx_buffer):
                        print(f"[rpi] Received message: {rx_buffer.decode('ascii', errors='ignore')}")
                    rx_buffer.clear()
                else:
                    rx_buffer.clear()


if __name__ == "__main__":
    main()
