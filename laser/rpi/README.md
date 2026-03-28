# Raspberry Pi Light Tracker

This folder currently contains a simple servo direction test for the Raspberry Pi.

## What it does

- centers both servos
- nudges the tilt servo very slightly in the currently configured "up" direction
- helps verify whether `TILT_INVERT` needs to be flipped

## Default GPIO pins

- pan servo signal: `GPIO 18`
- tilt servo signal: `GPIO 19`

Edit `tracker_config.py` to change pins, servo range, or the size of the test nudge.

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

## UART Receiver

Use `radio_receiver.py` if you want the Raspberry Pi to talk directly to the
radio air module over UART instead of using the ATmega.

### Raspberry Pi UART pins

- Pi `GPIO 15 / RXD0` (physical pin 10) <- radio `TX`
- Pi `GPIO 14 / TXD0` (physical pin 8) -> radio `RX`
- Pi `GND` (for example physical pin 6) -> radio `GND`

Important:

- `TX` crosses to `RX`
- grounds must be shared
- the Pi UART is `3.3V` logic, so do not feed it a `5V` UART signal

On the Pi, make sure the hardware UART is enabled and the Linux serial console
is disabled on that UART, otherwise the port may be busy.

Run:

```bash
cd laser/rpi
python radio_receiver.py
```

This receiver now uses a framed packet protocol with:

- sequence numbers
- CRC16 packet validation
- ACK replies for valid packets
- noise rejection for invalid / partial UART data
