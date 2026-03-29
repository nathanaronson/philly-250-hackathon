# Philly 250 Hackathon

Buoy-mounted system for detecting underwater hazards (duct tape "mines") using a camera, a laser targeting system, and wireless telemetry.

## Architecture

```text
Buoy (Raspberry Pi 5)
  ├── cv/          — Camera + real-time underwater object detection
  ├── laser/rpi/   — Pan/tilt servo controller + radio transceiver
  └── rpi/         — GPS and IMU telemetry

Ground Station
  ├── esp32/       — ESP32-S3 USB-to-WiFi bridge (Pi → laptop)
  └── laser/       — Telemetry receiver and ground-side tooling
```

---

## Modules

### `cv/` — Underwater Object Detector

Real-time underwater object detection using a Raspberry Pi camera and OpenCV background subtraction. No model training required — the system learns the empty scene on startup and flags anything that appears.

#### How it works

1. **Calibration** — on startup, point the camera at the empty tank. The background model learns what "nothing" looks like over ~3 seconds.
2. **Detection** — once calibrated, any object that appears is highlighted with a bounding box.
3. **No training required** — works entirely on visual difference from the learned background.

#### Setup

On the Raspberry Pi:

```bash
git clone <repo-url>
cd philly-250-hackathon
bash cv/scripts/install_pi.sh
cd cv && uv run python main.py
```

On a dev machine (falls back to webcam index 0):

```bash
cd cv
uv sync
uv run python main.py
```

#### Controls

| Key         | Action                                                      |
| ----------- | ----------------------------------------------------------- |
| `Q` / `ESC` | Quit                                                        |
| `R`         | Reset — re-run calibration (keep tank empty after pressing) |
| `S`         | Save current frame as PNG                                   |

**Tuning** — all parameters are in [cv/config.py](cv/config.py):

| Parameter             | Default | Description                           |
| --------------------- | ------- | ------------------------------------- |
| `BG_HISTORY`          | 60      | Frames used to build background model |
| `BG_VAR_THRESHOLD`    | 40      | Sensitivity — lower = more sensitive  |
| `MIN_CONTOUR_AREA`    | 500     | Minimum blob size in pixels²          |
| `CALIBRATION_SECONDS` | 3       | Calibration duration                  |

If you get too many false positives (bubbles, lighting flicker), raise `BG_VAR_THRESHOLD` or `MIN_CONTOUR_AREA`.

#### Project structure

```text
cv/
├── main.py                  # Entry point
├── config.py                # All tunable parameters
├── pyproject.toml           # uv project + dependencies
├── camera/
│   └── capture.py           # Pi camera / webcam abstraction
├── detector/
│   ├── background.py        # MOG2 background subtraction
│   └── display.py           # Bounding box and overlay rendering
└── scripts/
    └── install_pi.sh        # One-time Pi setup script
```

---

### `laser/rpi/` — Pan/Tilt Servo Controller

Controls two servos (pan + tilt) on the Raspberry Pi for laser targeting. Includes a UART radio receiver for receiving targeting commands from the ground station and an IMU telemetry sender.

See [laser/rpi/README.md](laser/rpi/README.md) for wiring, GPIO pin assignments, and run instructions.

---

### `esp32/` — USB-to-WiFi Bridge

Firmware for an Adafruit ESP32-S3 Feather that bridges USB Serial from the Raspberry Pi to a Flask server on the ground station laptop over WiFi.

```text
Raspberry Pi --USB Serial--> ESP32-S3 --WiFi HTTP POST--> Laptop Flask server
```

See [esp32/README.md](esp32/README.md) for flashing instructions and configuration.

---

### `rpi/` — Onboard Telemetry

GPS and IMU sensor modules running on the buoy Raspberry Pi.
