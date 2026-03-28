from pathlib import Path
import serial
import serial.tools.list_ports
import sys
import time


LASER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LASER_DIR))

from radio_protocol import PACKET_TYPE_ACK, PACKET_TYPE_DATA, PacketParser, build_packet


SERIAL_PORT = "COM3"
BAUD_RATE = 57600


def _format_imu_message(message: str) -> str:
    if not message.startswith("IMU,"):
        return message

    parts = message.split(",")
    if len(parts) != 8:
        return message

    _, ax, ay, az, gx, gy, gz, temp = parts
    return (
        f"accel(mg)=({ax}, {ay}, {az}) "
        f"gyro(mdps)=({gx}, {gy}, {gz}) "
        f"temp(C)={int(temp) / 100.0:.2f}"
    )


ports = [p.device for p in serial.tools.list_ports.comports()]
print("Found ports:", ports)

if SERIAL_PORT not in ports:
    print(f"{SERIAL_PORT} not found")
else:
    parser = PacketParser()

    print(f"{SERIAL_PORT} is plugged in")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1, write_timeout=0.25)
    time.sleep(2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    print("Listening for IMU packets")

    try:
        while True:
            incoming = ser.read(64)
            if not incoming:
                continue

            for packet in parser.feed(incoming):
                if packet.packet_type != PACKET_TYPE_DATA:
                    continue

                ser.write(build_packet(PACKET_TYPE_ACK, packet.sequence))
                ser.flush()

                try:
                    message = packet.payload.decode("ascii")
                except UnicodeDecodeError:
                    print(f"Received seq={packet.sequence} binary payload ({len(packet.payload)} bytes)")
                    continue

                print(f"Received seq={packet.sequence} {_format_imu_message(message)}")
    except KeyboardInterrupt:
        print("Stopped receiver")
    finally:
        ser.close()
