"""
Camera capture abstraction.

On a Raspberry Pi with the camera module attached, uses picamera2.
On any other machine (dev laptop, etc.), falls back to OpenCV webcam
so you can test the detection logic without Pi hardware.
"""

import sys
import numpy as np
import cv2
import config


def _is_raspberry_pi() -> bool:
    try:
        with open("/proc/device-tree/model") as f:
            return "Raspberry Pi" in f.read()
    except FileNotFoundError:
        return False


class PiCamera:
    def __init__(self):
        from picamera2 import Picamera2
        self._cam = Picamera2()
        self._cam.configure(
            self._cam.create_preview_configuration(
                main={"size": (config.FRAME_WIDTH, config.FRAME_HEIGHT)}
            )
        )
        self._cam.start()

    def read(self) -> tuple[bool, np.ndarray]:
        frame = self._cam.capture_array()
        # picamera2 returns XRGB/BGR — ensure 3-channel BGR for OpenCV
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return True, frame

    def release(self):
        self._cam.stop()


class WebcamCamera:
    def __init__(self, index: int = 0):
        self._cap = cv2.VideoCapture(index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, config.FRAME_RATE)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open webcam at index {index}")

    def read(self) -> tuple[bool, np.ndarray]:
        return self._cap.read()

    def release(self):
        self._cap.release()


def open_camera():
    """Return the appropriate camera for the current platform."""
    if _is_raspberry_pi():
        print("[camera] Detected Raspberry Pi — using picamera2")
        return PiCamera()
    else:
        print("[camera] Not a Pi — falling back to webcam (index 0) for dev/testing")
        return WebcamCamera()
