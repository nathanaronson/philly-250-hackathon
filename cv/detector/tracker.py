"""
IoU + centroid hybrid object tracker.

Matches detections to tracked objects using whichever score is higher:
  - IoU (bounding box overlap): great for large/irregular blobs
  - Expanded centroid distance: fallback when boxes don't overlap at all

This is more robust than pure centroid tracking when blobs change shape or
partially overlap as objects move (e.g. a head turning, a rock shifting).
"""

from dataclasses import dataclass
import math
from detector.background import Detection


# Minimum IoU to consider two boxes the same object (0-1)
IOU_THRESHOLD = 0.1

# Fallback: max centroid distance as fraction of the object's diagonal
# e.g. 1.5 means the centroid can move up to 1.5x the object's own size
MAX_MOVE_DIAG = 1.5

# Frames an object can be missing before it's considered gone
MAX_MISSING_FRAMES = 20

# Frames a new object must be visible before it's considered "established"
NEW_OBJECT_FRAMES = 10


def _iou(a: Detection, b: Detection) -> float:
    ax1, ay1, ax2, ay2 = a.x, a.y, a.x + a.w, a.y + a.h
    bx1, by1, bx2, by2 = b.x, b.y, b.x + b.w, b.y + b.h
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


def _match_score(obj_det: Detection, new_det: Detection) -> float:
    """Higher is better. Returns 0 if no match."""
    iou = _iou(obj_det, new_det)
    if iou >= IOU_THRESHOLD:
        return iou

    # Fallback: centroid distance relative to object size
    obj_cx = obj_det.x + obj_det.w / 2
    obj_cy = obj_det.y + obj_det.h / 2
    new_cx = new_det.x + new_det.w / 2
    new_cy = new_det.y + new_det.h / 2
    dist = math.hypot(new_cx - obj_cx, new_cy - obj_cy)
    diag = math.hypot(obj_det.w, obj_det.h)
    if diag > 0 and dist < MAX_MOVE_DIAG * diag:
        return 1.0 - (dist / (MAX_MOVE_DIAG * diag))  # 0-1 score

    return 0.0


@dataclass
class TrackedObject:
    id: int
    detection: Detection
    age: int = 0      # total frames seen
    missing: int = 0  # consecutive frames not matched

    @property
    def is_new(self) -> bool:
        return self.age < NEW_OBJECT_FRAMES


class ObjectTracker:
    def __init__(self):
        self._objects: dict[int, TrackedObject] = {}
        self._next_id = 0

    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        matched_ids: set[int] = set()
        matched_det: set[int] = set()

        # Greedily match each tracked object to its best detection
        for obj_id, obj in self._objects.items():
            best_score = 0.0
            best_idx = -1
            for i, det in enumerate(detections):
                if i in matched_det:
                    continue
                score = _match_score(obj.detection, det)
                if score > best_score:
                    best_score = score
                    best_idx = i

            if best_idx >= 0:
                obj.detection = detections[best_idx]
                obj.age += 1
                obj.missing = 0
                matched_ids.add(obj_id)
                matched_det.add(best_idx)

        # Unmatched tracked objects — age them out
        for obj_id, obj in list(self._objects.items()):
            if obj_id not in matched_ids:
                obj.missing += 1
                if obj.missing > MAX_MISSING_FRAMES:
                    del self._objects[obj_id]

        # Unmatched detections → new objects
        for i, det in enumerate(detections):
            if i not in matched_det:
                self._objects[self._next_id] = TrackedObject(
                    id=self._next_id, detection=det
                )
                self._next_id += 1

        return [o for o in self._objects.values() if o.missing == 0]
