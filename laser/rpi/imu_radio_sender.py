from __future__ import annotations

from pathlib import Path
import sys
import time

import serial

from lsm6dso import LSM6DSO


LASER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LASER_DIR))

from radio_protocol import PACKET_TYPE_ACK, PACKET_TYPE_DATA, PacketParser, build_packet


SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 57600
ACK_TIMEOUT_SECONDS = 0.20
SEND_INTERVAL_SECONDS = 0.05
MAX_RETRIES = 4


def _encode_sample(sample) -> bytes:
    # Compact ASCII payload to stay within the radio protocol size limit.
    return (
        f"IMU,{sample.accel_x_mg},{sample.accel_y_mg},{sample.accel_z_mg},"
        f"{sample.gyro_x_mdps},{sample.gyro_y_mdps},{sample.gyro_z_mdps},"
        f"{sample.temperature_centi_c}"
    ).encode("ascii")


def main() -> None:
    imu = LSM6DSO()
    parser = PacketParser()
    sequence = 0

    print(f"[rpi] Opening {SERIAL_PORT} at {BAUD_RATE} baud")
    print(f"[rpi] LSM6DSO found at 0x{imu.address:02X}")

    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.05, write_timeout=0.25) as ser:
        time.sleep(0.25)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print("[rpi] Streaming IMU packets")

        try:
            while True:
                sample = imu.read_sample()
                payload = _encode_sample(sample)
                packet = build_packet(PACKET_TYPE_DATA, sequence, payload)
                acknowledged = False

                for attempt in range(1, MAX_RETRIES + 1):
                    ser.write(packet)
                    ser.flush()

                    deadline = time.monotonic() + ACK_TIMEOUT_SECONDS
                    while time.monotonic() < deadline:
                        incoming = ser.read(64)
                        if not incoming:
                            continue

                        for received_packet in parser.feed(incoming):
                            if (
                                received_packet.packet_type == PACKET_TYPE_ACK
                                and received_packet.sequence == sequence
                            ):
                                acknowledged = True
                                break

                        if acknowledged:
                            break

                    if acknowledged:
                        break

                if acknowledged:
                    print(
                        f"[rpi] Sent seq={sequence} "
                        f"ax={sample.accel_x_mg} ay={sample.accel_y_mg} az={sample.accel_z_mg}"
                    )
                else:
                    print(f"[rpi] Failed seq={sequence}")

                sequence = (sequence + 1) & 0xFF
                time.sleep(SEND_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("[rpi] Stopped")
        finally:
            imu.close()


if __name__ == "__main__":
    main()
