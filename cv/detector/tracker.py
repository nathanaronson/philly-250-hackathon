"""
Velocity-based object tracker.

Each tracked object maintains a smoothed velocity estimate. Every frame we
predict where it will be, then match predictions to new detections using IoU.
This handles fast-moving objects (person walking across frame) much better
than a pure centroid distance check.

Flow per frame:
  1. Predict each object's new position using its velocity
  2. Match predictions → detections via best IoU
  3. Update matched objects (refine velocity)
  4. Age out missing objects after MAX_MISSING_FRAMES
  5. Register unmatched detections as new objects
"""

from dataclasses import dataclass, field
import math
from detector.background import Detection


# IoU threshold between predicted box and detection to count as a match
IOU_MATCH_THRESHOLD = 0.05   # low — predictions may not overlap perfectly

# If IoU fails, fall back to centroid distance (as fraction of object diagonal)
MAX_MOVE_DIAG = 2.0

# Velocity smoothing — higher = more inertia, slower to change direction
VELOCITY_SMOOTH = 0.6

# Frames an object can be missing before its track is dropped.
# High value keeps mine tracks alive through brief occlusions / turbidity.
MAX_MISSING_FRAMES = 60

# Frames an object must be *consistently* visible before it is flagged as a threat.
# Noise blobs vanish within a few frames; a real object persists. This eliminates flicker.
CONFIRM_FRAMES = 20  # ~0.67s at 30fps — brief splashes / reflections never confirm


def _iou(ax, ay, aw, ah, bx, by, bw, bh) -> float:
    ix1 = max(ax, bx)
    iy1 = max(ay, by)
    ix2 = min(ax + aw, bx + bw)
    iy2 = min(ay + ah, by + bh)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _match_score(pred_x, pred_y, pred_w, pred_h, det: Detection) -> float:
    iou = _iou(pred_x, pred_y, pred_w, pred_h, det.x, det.y, det.w, det.h)
    if iou >= IOU_MATCH_THRESHOLD:
        return iou

    # Centroid distance fallback
    pcx = pred_x + pred_w / 2
    pcy = pred_y + pred_h / 2
    dcx = det.x + det.w / 2
    dcy = det.y + det.h / 2
    dist = math.hypot(dcx - pcx, dcy - pcy)
    diag = math.hypot(pred_w, pred_h)
    if diag > 0 and dist < MAX_MOVE_DIAG * diag:
        return 0.5 * (1.0 - dist / (MAX_MOVE_DIAG * diag))

    return 0.0


@dataclass
class TrackedObject:
    id: int
    detection: Detection
    vx: float = 0.0   # velocity in x (pixels/frame)
    vy: float = 0.0   # velocity in y
    age: int = 0
    missing: int = 0

    @property
    def is_confirmed(self) -> bool:
        """True once the object has been visible for CONFIRM_FRAMES consecutive frames.
        Noise blobs disappear before this threshold; real mines persist and trip it."""
        return self.age >= CONFIRM_FRAMES

    def predicted_box(self):
        """Predicted position next frame based on current velocity."""
        return (
            self.detection.x + int(self.vx),
            self.detection.y + int(self.vy),
            self.detection.w,
            self.detection.h,
        )

    def update(self, det: Detection):
        new_cx = det.x + det.w / 2
        old_cx = self.detection.x + self.detection.w / 2
        new_cy = det.y + det.h / 2
        old_cy = self.detection.y + self.detection.h / 2
        raw_vx = new_cx - old_cx
        raw_vy = new_cy - old_cy
        # Smooth velocity — don't react instantly to jitter
        self.vx = VELOCITY_SMOOTH * self.vx + (1 - VELOCITY_SMOOTH) * raw_vx
        self.vy = VELOCITY_SMOOTH * self.vy + (1 - VELOCITY_SMOOTH) * raw_vy
        self.detection = det
        self.age += 1
        self.missing = 0


class ObjectTracker:
    def __init__(self):
        self._objects: dict[int, TrackedObject] = {}
        self._next_id = 0

    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        matched_ids: set[int] = set()
        matched_det: set[int] = set()

        # Match each tracked object to its best detection using predicted position
        for obj_id, obj in self._objects.items():
            px, py, pw, ph = obj.predicted_box()
            best_score = 0.0
            best_idx = -1
            for i, det in enumerate(detections):
                if i in matched_det:
                    continue
                score = _match_score(px, py, pw, ph, det)
                if score > best_score:
                    best_score = score
                    best_idx = i

            if best_idx >= 0:
                obj.update(detections[best_idx])
                matched_ids.add(obj_id)
                matched_det.add(best_idx)

        # Age out missing objects
        for obj_id, obj in list(self._objects.items()):
            if obj_id not in matched_ids:
                obj.missing += 1
                if obj.missing > MAX_MISSING_FRAMES:
                    del self._objects[obj_id]

        # New objects from unmatched detections
        for i, det in enumerate(detections):
            if i not in matched_det:
                self._objects[self._next_id] = TrackedObject(
                    id=self._next_id, detection=det
                )
                self._next_id += 1

        return [o for o in self._objects.values() if o.missing == 0]
