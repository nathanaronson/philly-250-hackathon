from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

import serial


LASER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LASER_DIR))

from radio_protocol import PACKET_TYPE_ACK, PACKET_TYPE_DATA, PacketParser, build_packet


BAUD_RATE = 57600
ACK_TIMEOUT_SECONDS = 0.30
MAX_RETRIES = 5


def send_with_ack(
    ser: serial.Serial,
    parser: PacketParser,
    tx_sequence: int,
    payload_text: str,
) -> bool:
    packet = build_packet(PACKET_TYPE_DATA, tx_sequence, payload_text.encode("ascii"))

    for attempt in range(1, MAX_RETRIES + 1):
        ser.write(packet)
        ser.flush()
        print(f"[link] Sent seq={tx_sequence} attempt={attempt} payload={payload_text}")

        deadline = time.monotonic() + ACK_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            incoming = ser.read(64)
            if not incoming:
                continue

            for packet_in in parser.feed(incoming):
                if packet_in.packet_type == PACKET_TYPE_ACK and packet_in.sequence == tx_sequence:
                    print(f"[link] ACK seq={tx_sequence}")
                    return True

                if packet_in.packet_type == PACKET_TYPE_DATA:
                    ack = build_packet(PACKET_TYPE_ACK, packet_in.sequence)
                    ser.write(ack)
                    ser.flush()

                    try:
                        text = packet_in.payload.decode("ascii")
                    except UnicodeDecodeError:
                        continue

                    print(f"[link] Deferred incoming payload while waiting for ACK: {text}")

        print(f"[link] Retrying seq={tx_sequence}")

    return False


def run_counter_node(port: str, name: str, start_value: int, initiator: bool) -> None:
    packet_parser = PacketParser()
    tx_sequence = 0
    next_value_to_send = start_value

    print(f"[{name}] Opening {port} at {BAUD_RATE} baud")

    with serial.Serial(port, BAUD_RATE, timeout=0.05, write_timeout=0.25) as ser:
        time.sleep(0.25)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        if initiator:
            if send_with_ack(ser, packet_parser, tx_sequence, str(next_value_to_send)):
                next_value_to_send += 2
                tx_sequence = (tx_sequence + 1) & 0xFF
            else:
                print(f"[{name}] Failed to deliver initial value")

        print(f"[{name}] Listening for counter packets")

        while True:
            incoming = ser.read(64)
            if not incoming:
                continue

            for packet_in in packet_parser.feed(incoming):
                if packet_in.packet_type == PACKET_TYPE_ACK:
                    print(f"[{name}] Unexpected standalone ACK seq={packet_in.sequence}")
                    continue

                ack = build_packet(PACKET_TYPE_ACK, packet_in.sequence)
                ser.write(ack)
                ser.flush()

                try:
                    text = packet_in.payload.decode("ascii")
                    received_value = int(text)
                except (UnicodeDecodeError, ValueError):
                    print(f"[{name}] Ignored invalid payload")
                    continue

                print(f"[{name}] Received value {received_value}")

                expected_previous = next_value_to_send - 1
                if received_value != expected_previous:
                    print(
                        f"[{name}] Received {received_value}, "
                        f"but expected {expected_previous} before sending {next_value_to_send}"
                    )
                    continue

                if send_with_ack(ser, packet_parser, tx_sequence, str(next_value_to_send)):
                    next_value_to_send += 2
                    tx_sequence = (tx_sequence + 1) & 0xFF
                else:
                    print(f"[{name}] Failed to deliver {next_value_to_send}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-node radio counter test")
    parser.add_argument("--port", required=True, help="Serial port path, e.g. /dev/ttyUSB0 or /dev/serial0")
    parser.add_argument("--name", required=True, help="Friendly node name for logging")
    parser.add_argument("--start-value", type=int, required=True, help="First counter value this node should send")
    parser.add_argument("--initiator", action="store_true", help="Send the first number immediately on startup")
    args = parser.parse_args()

    run_counter_node(
        port=args.port,
        name=args.name,
        start_value=args.start_value,
        initiator=args.initiator,
    )


if __name__ == "__main__":
    main()
