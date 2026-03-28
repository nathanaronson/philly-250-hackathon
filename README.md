# Underwater Object Detector

Real-time underwater object detection using a Raspberry Pi camera module and OpenCV background subtraction. Built for the Philly 250 Hackathon.

## How It Works

1. **Calibration** — on startup, point the camera at the empty tank. The background model learns what "nothing" looks like over ~3 seconds.
2. **Detection** — once calibrated, any object that appears (rock, mine mockup, debris) is highlighted with a bounding box and confidence score.
3. **No training required** — works entirely on visual difference from the learned background.

## Setup

### On the Raspberry Pi

```bash
git clone <repo-url>
cd philly-250-hackathon
bash scripts/install_pi.sh
uv run python main.py
```

### On a Dev Machine (webcam fallback)

```bash
uv sync
uv run python main.py
```

The app auto-detects whether it's running on a Pi. On any other machine it falls back to webcam index 0.

## Controls

| Key         | Action                                                      |
| ----------- | ----------------------------------------------------------- |
| `Q` / `ESC` | Quit                                                        |
| `R`         | Reset — re-run calibration (keep tank empty after pressing) |
| `S`         | Save current frame as PNG                                   |

## Tuning

All parameters are in [config.py](config.py):

| Parameter             | Default | What it does                          |
| --------------------- | ------- | ------------------------------------- |
| `BG_HISTORY`          | 60      | Frames used to build background model |
| `BG_VAR_THRESHOLD`    | 40      | Sensitivity — lower = more sensitive  |
| `MIN_CONTOUR_AREA`    | 500     | Minimum blob size in pixels²          |
| `CALIBRATION_SECONDS` | 3       | How long calibration takes            |

If you're getting too many false positives (bubbles, lighting flicker), raise `BG_VAR_THRESHOLD` or `MIN_CONTOUR_AREA`.

## Project Structure

```text
├── main.py                  # Entry point
├── config.py                # All tunable parameters
├── camera/
│   └── capture.py           # Pi camera / webcam abstraction
├── detector/
│   ├── background.py        # MOG2 detection logic + confidence scoring
│   └── display.py           # Bounding box and overlay rendering
└── scripts/
    └── install_pi.sh        # One-time Pi setup script
```
