from pathlib import Path
import sys

import cv2

import tracker_config as cfg
from light_tracker import detect_light
from servo_control import PanTiltController


def _add_cv_camera_to_path():
    repo_root = Path(__file__).resolve().parents[2]
    cv_dir = repo_root / "cv"
    sys.path.insert(0, str(cv_dir))


_add_cv_camera_to_path()
from camera.capture import open_camera  # noqa: E402


def _normalized_error(detection):
    half_width = detection.width / 2.0
    half_height = detection.height / 2.0

    x_error = (detection.center_x - half_width) / half_width
    y_error = (detection.center_y - half_height) / half_height
    return x_error, y_error


def main():
    camera = open_camera()
    controller = PanTiltController()
    controller.start()

    print("[rpi] Starting light tracker")
    print(f"[rpi] Pan GPIO={cfg.PAN_GPIO_PIN}, Tilt GPIO={cfg.TILT_GPIO_PIN}")
    print("[rpi] Press Q or ESC to quit, C to re-center servos")

    try:
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                print("[rpi] Camera read failed")
                break

            detection, annotated = detect_light(frame)

            if detection is not None:
                x_error, y_error = _normalized_error(detection)
                controller.update(x_error, y_error)
                cv2.putText(
                    annotated,
                    f"x={x_error:+.2f} y={y_error:+.2f}",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )
            else:
                cv2.putText(
                    annotated,
                    "No bright light detected",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )

            if cfg.SHOW_WINDOW:
                cv2.imshow(cfg.WINDOW_NAME, annotated)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("c"):
                    controller.center()
            else:
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break

    finally:
        controller.cleanup()
        camera.release()
        cv2.destroyAllWindows()
        print("[rpi] Stopped")


if __name__ == "__main__":
    main()
