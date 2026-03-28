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

## LSM6DSO IMU Telemetry

Use `imu_radio_sender.py` on the Raspberry Pi if you want the Pi to read an
`LSM6DSO` over I2C and send the IMU data back to the ground module / PC over
the same packet protocol.

### Raspberry Pi I2C pins

- Pi `GPIO 2 / SDA1` (physical pin 3) -> LSM6DSO `SDA`
- Pi `GPIO 3 / SCL1` (physical pin 5) -> LSM6DSO `SCL`
- Pi `3.3V` (physical pin 1 or 17) -> LSM6DSO `VCC`
- Pi `GND` (for example physical pin 6) -> LSM6DSO `GND`

Important:

- use `3.3V`, not `5V`, for the LSM6DSO logic/power unless your breakout board
  explicitly supports 5V input
- enable I2C on the Pi in `raspi-config`
- install an I2C Python package such as `smbus2`

Run on the Pi:

```bash
cd laser/rpi
python imu_radio_sender.py
```

Use this on the ground-computer side:

```bash
cd laser/telemetry
python imu_ground_receiver.py
```

## Pi 4 <-> Pi 5 Counter Test

Use these scripts to test two-way radio communication between the two Raspberry
Pis using the shared packet/ACK protocol.

Behavior:

- Raspberry Pi 5 sends `1`
- Raspberry Pi 4 receives and ACKs `1`, then sends `2`
- Raspberry Pi 5 receives and ACKs `2`, then sends `3`
- this continues forever

### Which script runs where

On the Raspberry Pi 4:

```bash
cd laser/rpi
python pi4_counter_node.py
```

On the Raspberry Pi 5:

```bash
cd laser/rpi
python pi5_counter_node.py
```

### Serial ports assumed by the wrappers

- `pi4_counter_node.py` uses `/dev/serial0`
- `pi5_counter_node.py` auto-detects the first `/dev/ttyUSB*` or `/dev/ttyACM*`

If your radio appears on a different device, edit the `SERIAL_PORT` constant in
the matching wrapper script.

To verify the USB radio is recognized on the Pi 5, check:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
dmesg | tail -n 50
lsusb
```
