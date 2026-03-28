from pathlib import Path
import serial
import serial.tools.list_ports
import time
import sys

LASER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LASER_DIR))

from radio_protocol import PACKET_TYPE_ACK, PACKET_TYPE_DATA, PacketParser, build_packet


SERIAL_PORT = "COM3"
BAUD_RATE = 57600
ACK_TIMEOUT_SECONDS = 0.35
SEND_INTERVAL_SECONDS = 0.10
MAX_RETRIES = 5
START_VALUE = 1

ports = [p.device for p in serial.tools.list_ports.comports()]
print("Found ports:", ports)

if SERIAL_PORT not in ports:
    print(f"{SERIAL_PORT} not found")
else:
    parser = PacketParser()
    sequence = 0
    next_value = START_VALUE

    print(f"{SERIAL_PORT} is plugged in")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.05, write_timeout=0.25)
    time.sleep(2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    try:
        while True:
            payload_text = str(next_value)
            packet = build_packet(
                packet_type=PACKET_TYPE_DATA,
                sequence=sequence,
                payload=payload_text.encode("ascii"),
            )
            acknowledged = False

            for attempt in range(1, MAX_RETRIES + 1):
                ser.write(packet)
                ser.flush()
                print(f"Sent seq={sequence} attempt={attempt} payload={payload_text}")

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
                            print(f"ACK seq={sequence}")
                            acknowledged = True
                            break

                    if acknowledged:
                        break

                if acknowledged:
                    break

                print(f"Retrying seq={sequence}")

            if not acknowledged:
                print(f"Failed to deliver seq={sequence}")
            else:
                next_value += 1

            sequence = (sequence + 1) & 0xFF
            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Stopped sending")
    finally:
        ser.close()