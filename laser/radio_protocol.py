from __future__ import annotations

from dataclasses import dataclass


START_BYTE = 0xAA
PROTOCOL_VERSION = 0x01

PACKET_TYPE_DATA = 0x01
PACKET_TYPE_ACK = 0x02
PACKET_TYPE_HELLO = 0x03

MAX_PAYLOAD_SIZE = 64
HEADER_SIZE = 5
CRC_SIZE = 2


@dataclass
class Packet:
    packet_type: int
    sequence: int
    payload: bytes


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF

    for byte in data:
        crc ^= byte << 8

        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF

    return crc


def build_packet(packet_type: int, sequence: int, payload: bytes = b"") -> bytes:
    if len(payload) > MAX_PAYLOAD_SIZE:
        raise ValueError("payload too large")

    body = bytes(
        [
            PROTOCOL_VERSION,
            packet_type & 0xFF,
            sequence & 0xFF,
            len(payload) & 0xFF,
        ]
    ) + payload
    crc = crc16_ccitt(body)

    return bytes([START_BYTE]) + body + crc.to_bytes(2, "big")


class PacketParser:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[Packet]:
        packets: list[Packet] = []
        self.buffer.extend(data)

        while True:
            if len(self.buffer) < HEADER_SIZE + CRC_SIZE:
                break

            try:
                start_index = self.buffer.index(START_BYTE)
            except ValueError:
                self.buffer.clear()
                break

            if start_index > 0:
                del self.buffer[:start_index]

            if len(self.buffer) < HEADER_SIZE + CRC_SIZE:
                break

            version = self.buffer[1]
            payload_length = self.buffer[4]

            if version != PROTOCOL_VERSION or payload_length > MAX_PAYLOAD_SIZE:
                del self.buffer[0]
                continue

            packet_length = HEADER_SIZE + payload_length + CRC_SIZE
            if len(self.buffer) < packet_length:
                break

            packet_bytes = bytes(self.buffer[:packet_length])
            body = packet_bytes[1:-2]
            received_crc = int.from_bytes(packet_bytes[-2:], "big")
            calculated_crc = crc16_ccitt(body)

            if received_crc != calculated_crc:
                del self.buffer[0]
                continue

            packets.append(
                Packet(
                    packet_type=packet_bytes[2],
                    sequence=packet_bytes[3],
                    payload=packet_bytes[5:-2],
                )
            )
            del self.buffer[:packet_length]

        return packets
