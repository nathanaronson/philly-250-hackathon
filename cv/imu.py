"""
LSM6DSO IMU reader with complementary filter.

Runs at 50 Hz over I2C (I2C-1 on Raspberry Pi).
Produces pitch / roll (absolute, from gravity) and yaw (gyro-integrated,
periodically corrected from GPS course-over-ground).

Falls back silently to (0, 0, 0) when no hardware is found so the CV
pipeline works on a dev machine without an IMU.

Filter:
  pitch, roll  = 98 % gyro + 2 % accelerometer  (complementary)
  yaw          = 100 % gyro + soft GPS nudge when moving
"""
from __future__ import annotations

import math
import sys
import time
import threading
from pathlib import Path

# Reach the shared lsm6dso driver without copying it
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "laser" / "rpi"))

_ALPHA        = 0.98   # gyro weight; 1-_ALPHA goes to accelerometer
_READ_HZ      = 50
_GPS_YAW_W    = 0.05   # fraction GPS heading pulls yaw each correction call
_GYRO_DEADBAND = 0.3   # deg/s — ignore tiny gyro noise below this threshold

imu_ok: bool = False   # set True once hardware is confirmed


class _Filter:
    def __init__(self):
        self._lock  = threading.Lock()
        self.pitch  = 0.0   # deg  (+) nose-up
        self.roll   = 0.0   # deg  (+) right
        self.yaw    = 0.0   # deg  0 = North, increases clockwise
        self._last  = time.monotonic()

    def update(self, ax_mg, ay_mg, az_mg, gx_mdps, gy_mdps, gz_mdps):
        now = time.monotonic()
        dt  = now - self._last
        self._last = now
        if dt <= 0 or dt > 1.0:
            return

        ax = ax_mg / 1000.0
        ay = ay_mg / 1000.0
        az = az_mg / 1000.0

        gx_d = gx_mdps / 1000.0   # deg/s
        gy_d = gy_mdps / 1000.0
        gz_d = gz_mdps / 1000.0

        # Dead-band: suppress noise when sensor is nearly still
        if abs(gx_d) < _GYRO_DEADBAND: gx_d = 0.0
        if abs(gy_d) < _GYRO_DEADBAND: gy_d = 0.0
        if abs(gz_d) < _GYRO_DEADBAND: gz_d = 0.0

        # Accel-derived pitch & roll (absolute reference via gravity)
        norm = math.sqrt(ax*ax + ay*ay + az*az)
        if norm > 0.1:
            ax_n = ax / norm
            ay_n = ay / norm
            az_n = az / norm
            pitch_a = math.degrees(math.atan2(-ax_n, math.sqrt(ay_n*ay_n + az_n*az_n)))
            roll_a  = math.degrees(math.atan2(ay_n, az_n))
        else:
            with self._lock:
                pitch_a, roll_a = self.pitch, self.roll

        with self._lock:
            self.pitch = _ALPHA * (self.pitch + gy_d * dt) + (1 - _ALPHA) * pitch_a
            self.roll  = _ALPHA * (self.roll  + gx_d * dt) + (1 - _ALPHA) * roll_a
            self.yaw   = (self.yaw + gz_d * dt) % 360.0

    def nudge_yaw(self, gps_hdg_deg: float):
        """Softly correct yaw toward GPS course-over-ground heading."""
        with self._lock:
            diff = ((gps_hdg_deg - self.yaw) + 180.0) % 360.0 - 180.0
            self.yaw = (self.yaw + _GPS_YAW_W * diff) % 360.0

    def get(self) -> tuple[float, float, float]:
        with self._lock:
            return self.pitch, self.roll, self.yaw


_filt = _Filter()


def imu_loop() -> None:
    """Blocking read loop — call in a daemon thread."""
    global imu_ok
    try:
        from lsm6dso import LSM6DSO  # noqa: PLC0415
        sensor = LSM6DSO()
        print(f"[imu] LSM6DSO found at 0x{sensor.address:02X} — orientation tracking active")
        imu_ok = True
        period = 1.0 / _READ_HZ
        while True:
            try:
                s = sensor.read_sample()
                _filt.update(
                    s.accel_x_mg, s.accel_y_mg, s.accel_z_mg,
                    s.gyro_x_mdps, s.gyro_y_mdps, s.gyro_z_mdps,
                )
            except Exception:
                pass
            time.sleep(period)
    except Exception as exc:
        print(f"[imu] No IMU hardware ({exc}) — mine positions will use camera GPS directly")


def nudge_yaw(gps_heading_deg: float) -> None:
    """Call from GPS loop whenever a valid course-over-ground is available."""
    _filt.nudge_yaw(gps_heading_deg)


def get_orientation() -> tuple[float, float, float]:
    """Returns (pitch_deg, roll_deg, yaw_deg)."""
    return _filt.get()
