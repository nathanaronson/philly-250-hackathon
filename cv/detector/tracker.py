"""
Single-target tracker tuned for the demo.

The detector may still produce a few candidate blobs, but for the demo we only
want one object to become "the mine": whichever new object appears and stays in
view. This tracker keeps a single active target, smooths its box, and resists
jumping to nearby noise.
"""

from dataclasses import dataclass, field
import math

import config
from detector.background import Detection


MIN_MATCH_SCORE = 0.20


def _iou(ax: int, ay: int, aw: int, ah: int, bx: int, by: int, bw: int, bh: int) -> float:
    ix1 = max(ax, bx)
    iy1 = max(ay, by)
    ix2 = min(ax + aw, bx + bw)
    iy2 = min(ay + ah, by + bh)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _match_score(pred_x: int, pred_y: int, pred_w: int, pred_h: int, det: Detection) -> float:
    iou = _iou(pred_x, pred_y, pred_w, pred_h, det.x, det.y, det.w, det.h)

    pcx = pred_x + pred_w / 2
    pcy = pred_y + pred_h / 2
    dcx = det.x + det.w / 2
    dcy = det.y + det.h / 2
    dist = math.hypot(dcx - pcx, dcy - pcy)
    diag = max(math.hypot(pred_w, pred_h), 1.0)
    dist_score = max(0.0, 1.0 - dist / (config.TRACK_MAX_MOVE_DIAG * diag))

    width_ratio = min(pred_w, det.w) / max(pred_w, det.w) if pred_w > 0 and det.w > 0 else 0.0
    height_ratio = min(pred_h, det.h) / max(pred_h, det.h) if pred_h > 0 and det.h > 0 else 0.0
    size_score = (width_ratio + height_ratio) / 2

    return (0.5 * iou) + (0.35 * dist_score) + (0.15 * size_score)


@dataclass
class TrackedObject:
    id: int
    detection: Detection
    vx: float = 0.0
    vy: float = 0.0
    age: int = 1
    missing: int = 0
    cx: float = field(init=False)
    cy: float = field(init=False)
    w: float = field(init=False)
    h: float = field(init=False)

    def __post_init__(self):
        self.cx = self.detection.x + self.detection.w / 2
        self.cy = self.detection.y + self.detection.h / 2
        self.w = float(self.detection.w)
        self.h = float(self.detection.h)

    @property
    def is_confirmed(self) -> bool:
        return self.age >= config.TRACK_CONFIRM_FRAMES

    def predicted_box(self) -> tuple[int, int, int, int]:
        return self._box_from_state(self.cx + self.vx, self.cy + self.vy, self.w, self.h)

    def mark_missing(self):
        self.cx += self.vx
        self.cy += self.vy
        self.missing += 1
        self._sync_detection(
            confidence=max(self.detection.confidence * 0.9, 0.0),
            area=self.detection.area,
        )

    def update(self, det: Detection):
        new_cx = det.x + det.w / 2
        new_cy = det.y + det.h / 2
        raw_vx = new_cx - self.cx
        raw_vy = new_cy - self.cy

        self.vx = 0.65 * self.vx + 0.35 * raw_vx
        self.vy = 0.65 * self.vy + 0.35 * raw_vy

        self.cx = (
            config.TRACK_POSITION_SMOOTHING * self.cx
            + (1 - config.TRACK_POSITION_SMOOTHING) * new_cx
        )
        self.cy = (
            config.TRACK_POSITION_SMOOTHING * self.cy
            + (1 - config.TRACK_POSITION_SMOOTHING) * new_cy
        )
        self.w = (
            config.TRACK_SIZE_SMOOTHING * self.w
            + (1 - config.TRACK_SIZE_SMOOTHING) * det.w
        )
        self.h = (
            config.TRACK_SIZE_SMOOTHING * self.h
            + (1 - config.TRACK_SIZE_SMOOTHING) * det.h
        )

        self.age += 1
        self.missing = 0
        self._sync_detection(confidence=det.confidence, area=det.area)

    def _sync_detection(self, confidence: float, area: int):
        x, y, w, h = self._box_from_state(self.cx, self.cy, self.w, self.h)
        self.detection = Detection(x=x, y=y, w=w, h=h, confidence=confidence, area=area)

    @staticmethod
    def _box_from_state(cx: float, cy: float, w: float, h: float) -> tuple[int, int, int, int]:
        iw = max(int(round(w)), 1)
        ih = max(int(round(h)), 1)
        x = int(round(cx - iw / 2))
        y = int(round(cy - ih / 2))
        return x, y, iw, ih


class ObjectTracker:
    def __init__(self):
        self._active: TrackedObject | None = None
        self._next_id = 0

    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        if self._active is None:
            best = self._select_primary_detection(detections)
            if best is None:
                return []
            self._active = self._new_track(best)
            return [self._active]

        best_idx, best_score = self._best_match(detections)
        if best_idx >= 0 and best_score >= MIN_MATCH_SCORE:
            self._active.update(detections[best_idx])
            return [self._active]

        self._active.mark_missing()
        if self._active.missing > config.TRACK_MAX_MISSING_FRAMES:
            replacement = self._select_primary_detection(detections)
            self._active = self._new_track(replacement) if replacement is not None else None

        return [self._active] if self._active is not None else []

    def _best_match(self, detections: list[Detection]) -> tuple[int, float]:
        if self._active is None:
            return -1, 0.0

        px, py, pw, ph = self._active.predicted_box()
        best_idx = -1
        best_score = 0.0
        for i, det in enumerate(detections):
            score = _match_score(px, py, pw, ph, det)
            if score > best_score:
                best_idx = i
                best_score = score
        return best_idx, best_score

    @staticmethod
    def _select_primary_detection(detections: list[Detection]) -> Detection | None:
        if not detections:
            return None
        return max(detections, key=lambda det: (det.confidence, -det.area))

    def _new_track(self, det: Detection) -> TrackedObject:
        obj = TrackedObject(id=self._next_id, detection=det)
        self._next_id += 1
        return obj
