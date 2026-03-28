# Raspberry Pi Light Tracker

This folder contains a simple pan/tilt light tracker for the Raspberry Pi.

## What it does

- reuses the existing camera module code from `cv/camera/capture.py`
- detects the brightest red light spot in the frame
- can move two positional servos to keep that light near the image center

## Default GPIO pins

- pan servo signal: `GPIO 18`
- tilt servo signal: `GPIO 19`

Edit `tracker_config.py` to change pins, servo range, or detection tuning.

## Wiring

- servo signal wires -> `GPIO 18` and `GPIO 19`
- servo grounds -> Pi ground
- servo power -> external 5V supply
- external servo power ground must be tied to Pi ground

These are standard positional servos, so they should move to an angle and hold.
They are not expected to spin continuously.

Do not power servos directly from the Pi 5V rail unless you know your current draw is safe.

## Run

From the repo root on the Pi:

```bash
cd laser/rpi
python main.py
```

Controls:

- `Q` or `ESC` quits
- `C` re-centers both servos
