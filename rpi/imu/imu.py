import smbus2
import time
import struct

# LSM6DSO I2C address (SDO pin low = 0x6A, high = 0x6B)
# Change to 0x6B if i2cdetect shows 6b instead of 6a
I2C_ADDR = 0x6B

# Registers
WHO_AM_I  = 0x0F
CTRL1_XL  = 0x10  # accelerometer control
CTRL2_G   = 0x11  # gyroscope control
OUTX_L_A  = 0x28  # accelerometer data start

# Accelerometer: 104 Hz, ±2g -> sensitivity = 0.000061 g/LSB -> m/s²
ACCEL_SCALE = 0.000061 * 9.81
CALIBRATION_SAMPLES = 200
CALIBRATION_DELAY = 0.005  # seconds between samples


def init(bus):
    who = bus.read_byte_data(I2C_ADDR, WHO_AM_I)
    if who != 0x6C:
        raise RuntimeError(f"LSM6DSO not found (WHO_AM_I=0x{who:02X}, expected 0x6C)")

    # Accelerometer: 104 Hz, ±2g
    bus.write_byte_data(I2C_ADDR, CTRL1_XL, 0x40)
    # Gyroscope off (not needed for position)
    bus.write_byte_data(I2C_ADDR, CTRL2_G, 0x00)
    time.sleep(0.1)


def read_accel(bus):
    data = bus.read_i2c_block_data(I2C_ADDR, OUTX_L_A, 6)
    x, y, z = struct.unpack('<hhh', bytes(data))
    return x * ACCEL_SCALE, y * ACCEL_SCALE, z * ACCEL_SCALE


def calibrate(bus):
    """Average readings while stationary to get bias (including gravity on z)."""
    print("Calibrating — keep the IMU still...")
    bx, by, bz = 0.0, 0.0, 0.0
    for _ in range(CALIBRATION_SAMPLES):
        x, y, z = read_accel(bus)
        bx += x
        by += y
        bz += z
        time.sleep(CALIBRATION_DELAY)
    bx /= CALIBRATION_SAMPLES
    by /= CALIBRATION_SAMPLES
    bz /= CALIBRATION_SAMPLES
    print(f"Bias: x={bx:.4f} y={by:.4f} z={bz:.4f} m/s²")
    return bx, by, bz


def track_position(bus, bias, interval=0.02):
    """
    Double-integrate acceleration to estimate position.
    interval: seconds between samples (50 Hz default)
    Press Ctrl+C to stop.
    """
    bx, by, bz = bias
    vx, vy = 0.0, 0.0
    px, py = 0.0, 0.0

    print("\nTracking position. Press Ctrl+C to stop.")
    print(f"{'Time(s)':>8}  {'X (m)':>8}  {'Y (m)':>8}")

    start = time.time()
    last = start

    try:
        while True:
            now = time.time()
            dt = now - last
            if dt < interval:
                time.sleep(interval - dt)
                continue
            last = now

            ax, ay, az = read_accel(bus)
            ax -= bx
            ay -= by

            # Deadband: ignore noise below 0.02 m/s²
            if abs(ax) < 0.02:
                ax = 0.0
            if abs(ay) < 0.02:
                ay = 0.0

            vx += ax * dt
            vy += ay * dt
            px += vx * dt
            py += vy * dt

            elapsed = now - start
            print(f"{elapsed:8.2f}  {px:8.4f}  {py:8.4f}")

    except KeyboardInterrupt:
        print(f"\nFinal position: x={px:.4f} m, y={py:.4f} m")
        return px, py


if __name__ == "__main__":
    bus = smbus2.SMBus(1)
    init(bus)
    bias = calibrate(bus)
    track_position(bus, bias)
