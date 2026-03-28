"""
Rendering / overlay logic. Kept separate from detection so the two can
evolve independently (e.g. swap in a web UI without touching detector code).
"""

import cv2
import numpy as np
import config
from detector.background import Detection
from detector.tracker import TrackedObject


# BGR color palette
_GREEN  = (0, 210, 0)
_YELLOW = (0, 200, 255)
_RED    = (0, 60, 255)
_WHITE  = (255, 255, 255)
_BLACK  = (0, 0, 0)
_GRAY   = (160, 160, 160)


def _confidence_color(conf: float) -> tuple[int, int, int]:
    if conf >= config.HIGH_CONF:
        return _GREEN
    if conf >= config.MED_CONF:
        return _YELLOW
    return _RED


def draw_detections(frame: np.ndarray, tracked: list[TrackedObject]) -> np.ndarray:
    """Draw bounding boxes and confidence labels for each tracked object."""
    out = frame.copy()
    for obj in tracked:
        det = obj.detection
        color = _confidence_color(det.confidence)
        thickness = 3 if obj.is_new else 2
        cv2.rectangle(out, (det.x, det.y), (det.x + det.w, det.y + det.h), color, thickness)

        tag = "NEW" if obj.is_new else f"#{obj.id}"
        label = f"{tag}  {det.confidence:.0%}"
        (lw, lh), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        label_y = max(det.y - 8, lh + 4)
        cv2.rectangle(out, (det.x, label_y - lh - 4), (det.x + lw + 4, label_y + baseline), _BLACK, -1)
        cv2.putText(out, label, (det.x + 2, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

    return out


def draw_status_bar(frame: np.ndarray, tracked: list[TrackedObject]) -> np.ndarray:
    """Top status bar: CLEAR / OBJECT DETECTED + object count."""
    out = frame.copy()
    if tracked:
        best = max(o.detection.confidence for o in tracked)
        new_count = sum(1 for o in tracked if o.is_new)
        parts = [f"{len(tracked)} object{'s' if len(tracked) > 1 else ''}"]
        if new_count:
            parts.append(f"{new_count} NEW")
        text = "DETECTED  " + "  ".join(parts) + f"  best: {best:.0%}"
        color = _confidence_color(best)
    else:
        text = "CLEAR"
        color = _GREEN

    cv2.rectangle(out, (0, 0), (frame.shape[1], 44), _BLACK, -1)
    cv2.putText(out, text, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.85, color, 2)
    return out


def draw_calibrating(frame: np.ndarray, progress: float) -> np.ndarray:
    """Overlay shown while the background model is still learning."""
    out = frame.copy()
    # Dim the frame
    overlay = out.copy()
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], frame.shape[0]), _BLACK, -1)
    out = cv2.addWeighted(out, 0.5, overlay, 0.5, 0)

    msg = "Calibrating... keep tank empty"
    (tw, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
    cx = (frame.shape[1] - tw) // 2
    cv2.putText(out, msg, (cx, frame.shape[0] // 2 - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, _WHITE, 2)

    # Progress bar
    bar_x, bar_y, bar_w, bar_h = 80, frame.shape[0] // 2 + 10, frame.shape[1] - 160, 20
    cv2.rectangle(out, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), _GRAY, 2)
    fill = int(bar_w * progress)
    if fill > 0:
        cv2.rectangle(out, (bar_x, bar_y), (bar_x + fill, bar_y + bar_h), _GREEN, -1)

    return out


def render(frame: np.ndarray, tracked: list[TrackedObject], is_calibrated: bool, calibration_progress: float) -> np.ndarray:
    """Single call to produce the final display frame."""
    if not is_calibrated:
        return draw_calibrating(frame, calibration_progress)
    frame = draw_detections(frame, tracked)
    frame = draw_status_bar(frame, tracked)
    return frame
