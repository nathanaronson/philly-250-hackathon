"""
Rendering / overlay logic.
"""

import time
import cv2
import numpy as np
import config
from detector.tracker import TrackedObject


# BGR equivalents of the website's CSS variables
_RED   = (68,  34,  255)   # --red:   #ff2244
_GREEN = (136, 255,   0)   # --green: #00ff88
_BLUE  = (255, 170,   0)   # --blue:  #00aaff
_WHITE = (255, 255, 255)
_BLACK = (  0,   0,   0)
_DIM   = ( 82,  51,  22)   # --border: #163352 — barely-visible box


def _is_mine(obj: TrackedObject, clip_scores: dict[int, float], mine_threshold: float) -> bool:
    """An object is flagged as a mine if confirmed AND either:
    - CLIP scored it above threshold, OR
    - CLIP hasn't scored it yet (still loading) — flag conservatively
    """
    if not obj.is_confirmed:
        return False
    score = clip_scores.get(obj.id)
    if score is None:
        return True   # CLIP not ready — flag anything confirmed
    return score >= mine_threshold


def draw_detections(
    frame: np.ndarray,
    objects: list[TrackedObject],
    clip_scores: dict[int, float],
    mine_threshold: float,
) -> np.ndarray:
    out = frame.copy()
    for obj in objects:
        d = obj.detection
        if not obj.is_confirmed:
            continue

        if _is_mine(obj, clip_scores, mine_threshold):
            # Thin red box — web UI handles the alert, keep overlay clean
            cv2.rectangle(out, (d.x, d.y), (d.x + d.w, d.y + d.h), _RED, 2)
            # Small label above box, no filled background
            label = "THREAT"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_PLAIN, 1.0, 1)
            label_y = max(d.y - 4, lh + 2)
            cv2.putText(out, label, (d.x, label_y), cv2.FONT_HERSHEY_PLAIN, 1.0, _RED, 1)
        else:
            cv2.rectangle(out, (d.x, d.y), (d.x + d.w, d.y + d.h), _DIM, 1)

    return out


def draw_alert(frame: np.ndarray, mine_objects: list[TrackedObject]) -> np.ndarray:
    """Full-frame red pulsing border + large centered text when mines present."""
    out = frame.copy()
    h, w = out.shape[:2]

    # Pulse border thickness using time so it visibly flashes
    pulse = int(abs(time.monotonic() % 1.0 - 0.5) * 40) + 8
    cv2.rectangle(out, (0, 0), (w - 1, h - 1), _RED, pulse)

    # Large centered alert text
    for i, line in enumerate([f"!! MINE DETECTED !!", f"{len(mine_objects)} object(s)"]):
        scale = 1.6 if i == 0 else 0.9
        thickness = 4 if i == 0 else 2
        (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_DUPLEX, scale, thickness)
        x = (w - tw) // 2
        y = h // 2 - 20 + i * (th + 20)
        # Shadow
        cv2.putText(out, line, (x + 3, y + 3), cv2.FONT_HERSHEY_DUPLEX, scale, _BLACK, thickness + 2)
        cv2.putText(out, line, (x, y), cv2.FONT_HERSHEY_DUPLEX, scale, _RED, thickness)

    return out


def draw_status_bar(
    frame: np.ndarray,
    objects: list[TrackedObject],
    clip_scores: dict[int, float],
    mine_threshold: float,
) -> np.ndarray:
    out = frame.copy()
    mines = [o for o in objects if _is_mine(o, clip_scores, mine_threshold)]

    if mines:
        best_score = max((clip_scores.get(o.id) or 0.0) for o in mines)
        text = f"!! MINE DETECTED ({len(mines)}) conf:{best_score:.0%} !!"
        bg, fg = _RED, _WHITE
    else:
        text = "CLEAR"
        bg, fg = _BLACK, _GREEN

    cv2.rectangle(out, (0, 0), (frame.shape[1], 50), bg, -1)
    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 1.0, 2)
    cx = (frame.shape[1] - tw) // 2
    cv2.putText(out, text, (cx, 36), cv2.FONT_HERSHEY_DUPLEX, 1.0, fg, 2)
    return out


def draw_calibrating(frame: np.ndarray, progress: float) -> np.ndarray:
    h, w = frame.shape[:2]

    # Dark navy background — matches UI panel color
    out = np.full_like(frame, (40, 31, 13))  # BGR for #0d1f28

    # Corner brackets in blue
    _BLUE = (255, 170, 0)  # BGR for #00aaff
    sz, t = 20, 2
    for x, y, dx, dy in [(10,10,1,1),(w-10,10,-1,1),(10,h-10,1,-1),(w-10,h-10,-1,-1)]:
        cv2.line(out, (x, y), (x + dx*sz, y), _BLUE, t)
        cv2.line(out, (x, y), (x, y + dy*sz), _BLUE, t)

    # Top label — small, dim
    top = "// AQUASCAN // INITIALIZING SENSOR BASELINE //"
    (tw, _), _ = cv2.getTextSize(top, cv2.FONT_HERSHEY_PLAIN, 1.0, 1)
    cv2.putText(out, top, ((w - tw) // 2, 36),
                cv2.FONT_HERSHEY_PLAIN, 1.0, (100, 80, 30), 1)

    # Main status text
    msg = "CALIBRATING"
    (tw, th), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_DUPLEX, 1.6, 3)
    cv2.putText(out, msg, ((w - tw) // 2, h // 2 - 30),
                cv2.FONT_HERSHEY_DUPLEX, 1.6, _GREEN, 3)

    # Subtext
    sub = "HOLD SCENE STILL"
    (sw, _), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_PLAIN, 1.2, 1)
    cv2.putText(out, sub, ((w - sw) // 2, h // 2 + 10),
                cv2.FONT_HERSHEY_PLAIN, 1.2, (100, 150, 80), 1)

    # Progress bar
    bar_x, bar_y = 60, h // 2 + 36
    bar_w, bar_h = w - 120, 8
    cv2.rectangle(out, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (60, 50, 20), -1)
    fill = int(bar_w * progress)
    if fill > 0:
        cv2.rectangle(out, (bar_x, bar_y), (bar_x + fill, bar_y + bar_h), _GREEN, -1)

    # Percentage
    pct = f"{int(progress * 100)}%"
    (pw, _), _ = cv2.getTextSize(pct, cv2.FONT_HERSHEY_PLAIN, 1.0, 1)
    cv2.putText(out, pct, ((w - pw) // 2, h // 2 + 60),
                cv2.FONT_HERSHEY_PLAIN, 1.0, _GREEN, 1)

    return out


def render(
    frame: np.ndarray,
    objects: list[TrackedObject],
    clip_scores: dict[int, float],
    is_calibrated: bool,
    calibration_progress: float,
    mine_threshold: float = 0.15,
) -> np.ndarray:
    if not is_calibrated:
        return draw_calibrating(frame, calibration_progress)

    mines = [o for o in objects if _is_mine(o, clip_scores, mine_threshold)]

    frame = draw_detections(frame, objects, clip_scores, mine_threshold)
    # draw_alert removed — browser UI handles threat overlays
    return frame
