"""
Quick sanity checks for camera and detection pipeline.
Usage: uv run python scripts/test_camera.py
"""

import sys
import cv2
sys.path.insert(0, ".")  # run from cv/

from camera.capture import open_camera
from detector.background import BackgroundDetector
from detector.display import render


def test_camera():
    print("\n--- Camera open ---")
    cam = open_camera()
    ok, frame = cam.read()
    print(f"ok:          {ok}")
    print(f"frame shape: {frame.shape if frame is not None else None}")
    cam.release()
    assert ok and frame is not None, "Camera failed to produce a frame"
    print("PASS")
    return True


def test_pipeline():
    print("\n--- Detection pipeline (5 frames) ---")
    cam = open_camera()
    det = BackgroundDetector()
    for i in range(5):
        ok, frame = cam.read()
        assert ok and frame is not None, f"Frame {i} failed"
        display = render(frame, det.process(frame), det.is_calibrated, det.calibration_progress)
        _, jpeg = cv2.imencode(".jpg", display)
        print(f"frame {i}: jpeg={len(jpeg.tobytes())} bytes  calibrated={det.is_calibrated}")
    cam.release()
    print("PASS")
    return True


if __name__ == "__main__":
    passed = 0
    for test in [test_camera, test_pipeline]:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {e}")

    print(f"\n{passed}/2 tests passed")
    sys.exit(0 if passed == 2 else 1)
