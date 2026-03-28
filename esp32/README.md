# ESP32-S3 USB-to-WiFi Bridge

This folder contains firmware for an Adafruit ESP32-S3 Feather that:

1. Reads text lines from USB Serial (CDC).
2. Sends each line over WiFi to a Flask server on your laptop.

The implementation is in `usb_wifi_bridge/usb_wifi_bridge.ino`.

## End-to-end demo topology

Raspberry Pi --USB Serial--> ESP32-S3 Feather --WiFi HTTP POST--> Laptop Flask server

Files:

- ESP32 firmware: `usb_wifi_bridge/usb_wifi_bridge.ino`
- Raspberry Pi sender: `raspberry_pi/send_usb_to_esp32.py`
- Laptop Flask receiver: `laptop_server/flask_server.py`

## Hardware / IDE requirements

- Board: Adafruit Feather ESP32-S3
- Arduino core for ESP32 installed
- In Arduino IDE, set:
  - USB CDC On Boot: `Enabled`

## 1) Start the Flask server on your laptop

1. Open a terminal in `esp32/laptop_server`.
2. Install dependencies:
  - `pip install -r requirements.txt`
3. Start server:
  - `python flask_server.py`
4. Verify:
  - `http://<laptop-ip>:5000/health`

## 2) Configure and flash the ESP32 firmware

1. Open `usb_wifi_bridge/usb_wifi_bridge.ino`.
2. Edit these constants in the sketch:
   - `WIFI_SSID`
   - `WIFI_PASS`
  - `SERVER_URL` (example: `http://192.168.1.50:5000/ingest`)
3. Build and flash to the ESP32-S3 Feather.

## 3) Run the Raspberry Pi USB demo sender

1. Connect Raspberry Pi to ESP32-S3 with USB.
2. On the Pi, open a terminal in `esp32/raspberry_pi`.
3. Install dependencies:
  - `pip install -r requirements.txt`
4. Run:
  - `python send_usb_to_esp32.py --port /dev/ttyACM0 --count 10`

The Pi script sends lines over USB. The ESP32 replies over USB with ACK lines:

- `ACK|1|200` means Flask accepted the message.
- `ACK|0|...` means forwarding failed.

You can view posted messages at:

- `http://<laptop-ip>:5000/messages`

## Notes

- If WiFi drops, the firmware reconnects automatically.
- Messages are sent as HTTP JSON payloads to `/ingest`.
- Keep payloads reasonably small (line buffer is 512 chars by default).
