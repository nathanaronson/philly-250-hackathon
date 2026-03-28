"""
Camera capture abstraction.

On Raspberry Pi OS Bookworm the CSI camera uses the libcamera stack which
doesn't expose a standard V4L2 device OpenCV can read. Instead we spawn
rpicam-vid as a subprocess and pipe raw YUV420 frames into OpenCV.

On any other machine (dev laptop) we fall back to cv2.VideoCapture (webcam).
"""

import subprocess
import time
import cv2
import numpy as np
import config


def _is_raspberry_pi() -> bool:
    try:
        with open("/proc/device-tree/model") as f:
            return "Raspberry Pi" in f.read()
    except FileNotFoundError:
        return False


class PiCamera:
    def __init__(self):
        self._w = config.FRAME_WIDTH
        self._h = config.FRAME_HEIGHT
        self._frame_bytes = self._w * self._h * 3 // 2  # YUV420 size

        base_args = [
            "--width", str(self._w),
            "--height", str(self._h),
            "--framerate", str(config.FRAME_RATE),
            "--codec", "yuv420",
            "--output", "-",
            "--nopreview",
            "--timeout", "0",
        ]

        stable_args: list[str] = []
        if getattr(config, "PI_STABILIZE_CONTROLS", False):
            stable_args = [
                "--autofocus-mode", getattr(config, "PI_AF_MODE", "auto"),
                "--awb", getattr(config, "PI_AWB_MODE", "auto"),
                "--denoise", getattr(config, "PI_DENOISE_MODE", "cdn_off"),
            ]

        # Try rpicam-vid (Bookworm) then libcamera-vid (Bullseye).
        # Start with stabilized controls; if unsupported, retry with base args.
        for cmd in ("rpicam-vid", "libcamera-vid"):
            for extra in (stable_args, []):
                try:
                    args = [cmd, *base_args, *extra]
                    proc = subprocess.Popen(
                        args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )

                    time.sleep(0.8)
                    if proc.poll() is not None:
                        err = (proc.stderr.read() or b"").decode("utf-8", errors="ignore").strip()
                        if extra:
                            print(f"[camera] {cmd} rejected stabilized args, falling back: {err[:120]}")
                        continue

                    self._proc = proc
                    print(f"[camera] Started {cmd} pipeline")
                    time.sleep(1.5)  # let controls settle before first read
                    print("[camera] Ready")
                    return
                except FileNotFoundError:
                    break
        raise RuntimeError("Neither rpicam-vid nor libcamera-vid found. Is the camera enabled?")

    def read(self) -> tuple[bool, np.ndarray]:
        raw = self._proc.stdout.read(self._frame_bytes)
        if len(raw) < self._frame_bytes:
            return False, None
        yuv = np.frombuffer(raw, dtype=np.uint8).reshape((self._h * 3 // 2, self._w))
        frame = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)
        return True, frame

    def release(self):
        self._proc.terminate()


class WebcamCamera:
    def __init__(self, index: int = 0):
        self._cap = cv2.VideoCapture(index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, config.FRAME_RATE)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open webcam at index {index}")
        print(f"[camera] Opened webcam at index {index}")

    def read(self) -> tuple[bool, np.ndarray]:
        return self._cap.read()

    def release(self):
        self._cap.release()


def open_camera():
    if _is_raspberry_pi():
        return PiCamera()
    return WebcamCamera()
