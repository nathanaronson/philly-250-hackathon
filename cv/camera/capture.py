"""
Camera capture abstraction.

Uses cv2.VideoCapture for all platforms:
- On Raspberry Pi OS Bookworm the CSI camera module is exposed as a V4L2
  device (/dev/video0) so OpenCV can open it directly — no picamera2 needed.
- On any dev machine this opens the default webcam.
"""

import cv2
import numpy as np
import config


class Camera:
    def __init__(self, index: int = 0):
        self._cap = cv2.VideoCapture(index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, config.FRAME_RATE)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Could not open camera at index {index}. "
                "On Pi, check 'sudo raspi-config' → Interface Options → Camera is enabled."
            )
        print(f"[camera] Opened camera at index {index}")

    def read(self) -> tuple[bool, np.ndarray]:
        return self._cap.read()

    def release(self):
        self._cap.release()


def open_camera() -> Camera:
    return Camera(index=0)
