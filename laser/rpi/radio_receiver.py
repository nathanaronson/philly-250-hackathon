"""
Simple Raspberry Pi UART receiver for the telemetry radio.

Default behavior:
- opens the Pi hardware UART on /dev/serial0
- listens at 57600 baud, 8N1
- accepts only valid framed packets with CRC16
- sends ACKs back for each valid data packet
- ignores random line noise that does not parse as a packet

Run on the Pi:
    python radio_receiver.py
"""

from __future__ import annotations

import time

import serial

from radio_protocol import (
    PACKET_TYPE_ACK,
    PACKET_TYPE_DATA,
    PacketParser,
    build_packet,
)


SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 57600
TIMEOUT_SECONDS = 0.2


def main() -> None:
    parser = PacketParser()

    print(f"[rpi] Opening {SERIAL_PORT} at {BAUD_RATE} baud")

    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT_SECONDS, write_timeout=0.25) as ser:
        time.sleep(0.25)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print("[rpi] Listening for radio data")

        while True:
            chunk = ser.read(64)
            if not chunk:
                continue

            for packet in parser.feed(chunk):
                if packet.packet_type == PACKET_TYPE_DATA:
                    ack = build_packet(PACKET_TYPE_ACK, packet.sequence)
                    ser.write(ack)
                    ser.flush()

                    try:
                        message = packet.payload.decode("utf-8")
                    except UnicodeDecodeError:
                        print(
                            f"[rpi] Received seq={packet.sequence} binary payload "
                            f"({len(packet.payload)} bytes)"
                        )
                    else:
                        print(f"[rpi] Received seq={packet.sequence} message: {message}")
                elif packet.packet_type == PACKET_TYPE_ACK:
                    print(f"[rpi] ACK seq={packet.sequence}")


if __name__ == "__main__":
    main()
