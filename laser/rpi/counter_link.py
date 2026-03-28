from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

import serial


LASER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LASER_DIR))

from radio_protocol import (
    PACKET_TYPE_ACK,
    PACKET_TYPE_DATA,
    PACKET_TYPE_HELLO,
    PacketParser,
    build_packet,
)


BAUD_RATE = 57600
ACK_TIMEOUT_SECONDS = 0.12
MAX_RETRIES = 3
HELLO_INTERVAL_SECONDS = 0.25
COUNTER_RETRY_INTERVAL_SECONDS = 0.10


def _encode_counter(value: int) -> bytes:
    return int(value & 0xFFFFFFFF).to_bytes(4, "big")


def _decode_counter(payload: bytes) -> int:
    if len(payload) != 4:
        raise ValueError("counter payload must be 4 bytes")

    return int.from_bytes(payload, "big")


def send_with_ack(
    ser: serial.Serial,
    parser: PacketParser,
    packet_type: int,
    tx_sequence: int,
    payload: bytes,
) -> bool:
    packet = build_packet(packet_type, tx_sequence, payload)

    for attempt in range(1, MAX_RETRIES + 1):
        ser.write(packet)
        ser.flush()
        if packet_type == PACKET_TYPE_DATA:
            print(f"[link] Sent seq={tx_sequence} attempt={attempt}")

        deadline = time.monotonic() + ACK_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            incoming = ser.read(64)
            if not incoming:
                continue

            for packet_in in parser.feed(incoming):
                if packet_in.packet_type == PACKET_TYPE_ACK and packet_in.sequence == tx_sequence:
                    print(f"[link] ACK seq={tx_sequence}")
                    return True

                if packet_in.packet_type in (PACKET_TYPE_DATA, PACKET_TYPE_HELLO):
                    ack = build_packet(PACKET_TYPE_ACK, packet_in.sequence)
                    ser.write(ack)
                    ser.flush()

                    if packet_in.packet_type == PACKET_TYPE_DATA:
                        try:
                            deferred_value = _decode_counter(packet_in.payload)
                        except ValueError:
                            continue

                        print(f"[link] Deferred incoming value while waiting for ACK: {deferred_value}")

        if packet_type == PACKET_TYPE_DATA:
            print(f"[link] Retrying seq={tx_sequence}")

    return False


def run_counter_node(port: str, name: str, start_value: int, initiator: bool) -> None:
    packet_parser = PacketParser()
    tx_sequence = 0
    next_value_to_send = start_value
    initial_counter_sent = False
    link_established = False
    next_hello_deadline = 0.0
    next_counter_deadline = 0.0

    print(f"[{name}] Opening {port} at {BAUD_RATE} baud")

    with serial.Serial(port, BAUD_RATE, timeout=0.005, write_timeout=0.10) as ser:
        time.sleep(0.25)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        print(f"[{name}] Listening for counter packets")

        while True:
            now = time.monotonic()

            if (not link_established) and now >= next_hello_deadline:
                if send_with_ack(ser, packet_parser, PACKET_TYPE_HELLO, tx_sequence, b""):
                    tx_sequence = (tx_sequence + 1) & 0xFF
                next_hello_deadline = now + HELLO_INTERVAL_SECONDS

            if initiator and (not initial_counter_sent) and now >= next_counter_deadline:
                if send_with_ack(
                    ser,
                    packet_parser,
                    PACKET_TYPE_DATA,
                    tx_sequence,
                    _encode_counter(next_value_to_send),
                ):
                    next_value_to_send += 2
                    tx_sequence = (tx_sequence + 1) & 0xFF
                    initial_counter_sent = True
                    link_established = True
                else:
                    print(f"[{name}] Failed to deliver initial value")

                next_counter_deadline = now + COUNTER_RETRY_INTERVAL_SECONDS

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

                if packet_in.packet_type == PACKET_TYPE_HELLO:
                    continue

                if packet_in.packet_type != PACKET_TYPE_DATA:
                    print(f"[{name}] Ignored packet type {packet_in.packet_type}")
                    continue

                try:
                    received_value = _decode_counter(packet_in.payload)
                except ValueError:
                    print(f"[{name}] Ignored invalid counter payload")
                    continue

                print(f"[{name}] Received value {received_value}")
                link_established = True

                expected_previous = next_value_to_send - 1
                if received_value != expected_previous:
                    print(
                        f"[{name}] Received {received_value}, "
                        f"but expected {expected_previous} before sending {next_value_to_send}"
                    )
                    continue

                if send_with_ack(
                    ser,
                    packet_parser,
                    PACKET_TYPE_DATA,
                    tx_sequence,
                    _encode_counter(next_value_to_send),
                ):
                    next_value_to_send += 2
                    tx_sequence = (tx_sequence + 1) & 0xFF
                    initial_counter_sent = True
                    link_established = True
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
