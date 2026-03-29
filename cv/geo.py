"""
Projects a detected pixel through the camera model and IMU orientation
onto the water surface plane to estimate a mine's GPS coordinates.

Coordinate conventions
----------------------
Camera frame  (standard pinhole): x = right, y = down, z = forward
Body frame    (aerospace NED):     x = forward, y = right, z = down
World frame   (NED):               x = North,   y = East,  z = Down

Euler angles (from IMU, all degrees)
  yaw   – heading of body/camera forward axis  (0 = North, CW positive)
  pitch – nose up / down                       (+up, -down)
  roll  – right tilt                           (+right)

Mount offsets (from config)
  CAMERA_MOUNT_PITCH_DEG  – how many degrees the camera is physically
                            tilted down from the body's level plane.
                            e.g. -45 means the camera faces 45° below horizontal.
  CAMERA_MOUNT_ROLL_DEG   – physical roll of the camera relative to body.
"""
from __future__ import annotations

import math


# ── minimal pure-Python 3×3 linear algebra ──────────────────────────────────

def _mv(M, v):
    """3×3 matrix × 3-vector."""
    return [
        M[0][0]*v[0] + M[0][1]*v[1] + M[0][2]*v[2],
        M[1][0]*v[0] + M[1][1]*v[1] + M[1][2]*v[2],
        M[2][0]*v[0] + M[2][1]*v[1] + M[2][2]*v[2],
    ]

def _mm(A, B):
    """3×3 × 3×3."""
    return [
        [sum(A[r][k]*B[k][c] for k in range(3)) for c in range(3)]
        for r in range(3)
    ]

def _Rx(a):
    c, s = math.cos(a), math.sin(a)
    return [[1,0,0],[0,c,-s],[0,s,c]]

def _Ry(a):
    c, s = math.cos(a), math.sin(a)
    return [[c,0,s],[0,1,0],[-s,0,c]]

def _Rz(a):
    c, s = math.cos(a), math.sin(a)
    return [[c,-s,0],[s,c,0],[0,0,1]]


# ── public API ───────────────────────────────────────────────────────────────

def project(
    u: float, v: float,
    lat: float, lon: float,
    pitch_deg: float, roll_deg: float, yaw_deg: float,
    camera_height_m: float,
    hfov_deg: float, vfov_deg: float,
    frame_w: int, frame_h: int,
) -> tuple[float, float] | None:
    """
    Return estimated (mine_lat, mine_lon), or None if the ray misses water.

    u, v            – pixel coordinates of the mine centroid
    lat, lon        – camera GPS position
    pitch/roll/yaw  – total camera orientation (IMU angles + mount offsets)
    camera_height_m – camera height above the water surface
    hfov_deg/vfov_deg – camera horizontal / vertical field of view
    frame_w/h       – image resolution
    """
    # 1. Pixel → normalised ray in camera frame (x=right, y=down, z=fwd)
    fx = (frame_w / 2.0) / math.tan(math.radians(hfov_deg / 2.0))
    fy = (frame_h / 2.0) / math.tan(math.radians(vfov_deg / 2.0))
    rx = (u - frame_w / 2.0) / fx
    ry = (v - frame_h / 2.0) / fy
    rz = 1.0
    n  = math.sqrt(rx*rx + ry*ry + rz*rz)
    ray_cam = [rx/n, ry/n, rz/n]

    # 2. Camera frame → body frame (x=fwd, y=right, z=down)
    ray_body = [ray_cam[2], ray_cam[0], ray_cam[1]]

    # 3. Body → NED via ZYX Euler rotation
    p = math.radians(pitch_deg)
    r = math.radians(roll_deg)
    y = math.radians(yaw_deg)
    R = _mm(_Rz(y), _mm(_Ry(p), _Rx(r)))
    ray_ned = _mv(R, ray_body)   # [north, east, down]

    # 4. Intersect with horizontal water plane
    #    Camera is camera_height_m above water → water at NED-z = +camera_height_m
    #    Parametric: P = t * ray_ned;  want P[2] = camera_height_m
    if ray_ned[2] <= 0:
        return None  # ray points upward, never reaches water

    t        = camera_height_m / ray_ned[2]
    north_m  = t * ray_ned[0]
    east_m   = t * ray_ned[1]

    # 5. Metric offset → GPS
    dlat = north_m / 111320.0
    dlon = east_m  / (111320.0 * math.cos(math.radians(lat)))

    return lat + dlat, lon + dlon
