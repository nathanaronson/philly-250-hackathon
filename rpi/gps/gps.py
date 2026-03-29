import serial
import pynmea2
import time

PORT = "/dev/ttyAMA0"
BAUD = 9600


def read_gps():
    print("Waiting for GPS fix... (may take up to 60s outdoors)")
    with serial.Serial(PORT, BAUD, timeout=1) as ser:
        while True:
            try:
                line = ser.readline().decode("ascii", errors="replace").strip()
                if line.startswith("$GPRMC") or line.startswith("$GNRMC"):
                    msg = pynmea2.parse(line)
                    if msg.status == "A":  # A = active/valid fix
                        print(f"Lat: {msg.latitude:.6f}  Lon: {msg.longitude:.6f}  Speed: {msg.spd_over_grnd:.1f} knots")
                    else:
                        print("No fix yet...")
            except pynmea2.ParseError:
                pass
            except KeyboardInterrupt:
                print("Stopped.")
                break


if __name__ == "__main__":
    read_gps()
