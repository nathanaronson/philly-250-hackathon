#!/usr/bin/env python3
"""Send demo lines from Raspberry Pi to ESP32-S3 over USB serial.

The ESP32 firmware forwards each line to a Flask server over WiFi and returns:
  ACK|<1 or 0>|<http_code_or_error>
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import sys
import time

import serial


def detect_default_port() -> str | None:
    candidates = sorted(glob.glob("/dev/ttyACM*")) + sorted(glob.glob("/dev/ttyUSB*"))
    return candidates[0] if candidates else None


def wait_for_ack(ser: serial.Serial, timeout_s: float) -> str | None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        raw = ser.readline()
        if not raw:
            continue

        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue

        print(f"RX <- {line}")
        if line.startswith("ACK|"):
            return line
    return None


def run_demo(port: str, baud: int, count: int, interval_s: float, ack_timeout_s: float) -> int:
    print(f"Opening serial port {port} at {baud} baud")

    with serial.Serial(port, baudrate=baud, timeout=0.2) as ser:
        # Many ESP32-S3 boards reset when serial opens.
        time.sleep(2.0)
        ser.reset_input_buffer()

        for seq in range(count):
            timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
            payload = f"pi_demo seq={seq} utc={timestamp}"
            ser.write((payload + "\n").encode("utf-8"))
            ser.flush()
            print(f"TX -> {payload}")

            ack = wait_for_ack(ser, timeout_s=ack_timeout_s)
            if ack is None:
                print("No ACK received before timeout")

            time.sleep(interval_s)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Demo USB serial sender for ESP32-S3 bridge")
    parser.add_argument("--port", default=None, help="Serial port (default: first /dev/ttyACM* or /dev/ttyUSB*)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--count", type=int, default=10, help="How many demo lines to send")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between messages")
    parser.add_argument("--ack-timeout", type=float, default=2.5, help="Seconds to wait for each ACK")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    port = args.port or detect_default_port()
    if not port:
        print("No serial port detected. Use --port, for example: /dev/ttyACM0", file=sys.stderr)
        return 2

    try:
        return run_demo(port, args.baud, args.count, args.interval, args.ack_timeout)
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
