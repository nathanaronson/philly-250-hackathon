"""
Underwater object detector — entry point.

Usage:
    python main.py

Controls:
    Q or ESC  — quit
    R         — reset background model (re-calibrate)
    S         — save current frame as PNG
"""

import sys
import time
import cv2

from camera.capture import open_camera
from detector.background import BackgroundDetector
from detector.display import render


WINDOW_NAME = "Underwater Detector"


def main():
    camera = open_camera()
    detector = BackgroundDetector()

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 800, 600)

    frame_count = 0
    print("[main] Starting — point camera at empty tank to calibrate.")
    print("[main] Controls: Q/ESC = quit | R = reset calibration | S = save frame")

    while True:
        ok, frame = camera.read()
        if not ok or frame is None:
            print("[main] Failed to read frame — exiting.")
            break

        detections = detector.process(frame)
        display = render(
            frame,
            detections,
            is_calibrated=detector.is_calibrated,
            calibration_progress=detector.calibration_progress,
        )

        cv2.imshow(WINDOW_NAME, display)
        frame_count += 1

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):  # Q or ESC
            break
        elif key == ord("r"):
            print("[main] Resetting background model — keep tank empty.")
            detector = BackgroundDetector()
        elif key == ord("s"):
            filename = f"frame_{int(time.time())}.png"
            cv2.imwrite(filename, display)
            print(f"[main] Saved {filename}")

    camera.release()
    cv2.destroyAllWindows()
    print(f"[main] Stopped after {frame_count} frames.")


if __name__ == "__main__":
    main()
