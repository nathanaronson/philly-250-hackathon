"""
Multi-object centroid/IoU tracker.

Each new detection is matched to an existing track by a combined IoU +
distance score.  Unmatched detections spawn new tracks; tracks that go
unmatched for too long are dropped.

Tracks created during normal operation only — new tracks are never created
while the detector is suppressing detections (camera movement).
"""

from dataclasses import dataclass, field
import math

import config
from detector.background import Detection


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


def _match_score(
    track_cx: float, track_cy: float, track_w: float, track_h: float,
    det: Detection,
    frame_diag: float,
) -> float:
    """Combined IoU + normalised centre-distance score (higher = better match)."""
    tx = int(track_cx - track_w / 2)
    ty = int(track_cy - track_h / 2)
    tw = int(track_w)
    th = int(track_h)

    iou = _iou(tx, ty, tw, th, det.x, det.y, det.w, det.h)

    dcx = det.x + det.w / 2
    dcy = det.y + det.h / 2
    dist = math.hypot(dcx - track_cx, dcy - track_cy)
    max_dist = config.TRACK_MAX_DIST_FRAC * frame_diag
    dist_score = max(0.0, 1.0 - dist / max_dist)

    return 0.5 * iou + 0.5 * dist_score


@dataclass
class TrackedObject:
    id: int
    detection: Detection
    age: int = 1
    missing: int = 0
    vx: float = 0.0
    vy: float = 0.0
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

    def update(self, det: Detection):
        new_cx = det.x + det.w / 2
        new_cy = det.y + det.h / 2

        raw_vx = new_cx - self.cx
        raw_vy = new_cy - self.cy
        self.vx = 0.6 * self.vx + 0.4 * raw_vx
        self.vy = 0.6 * self.vy + 0.4 * raw_vy

        alpha_pos = 1.0 - config.TRACK_POSITION_SMOOTHING
        alpha_sz = 1.0 - config.TRACK_SIZE_SMOOTHING

        self.cx = config.TRACK_POSITION_SMOOTHING * self.cx + alpha_pos * new_cx
        self.cy = config.TRACK_POSITION_SMOOTHING * self.cy + alpha_pos * new_cy
        self.w = config.TRACK_SIZE_SMOOTHING * self.w + alpha_sz * det.w
        self.h = config.TRACK_SIZE_SMOOTHING * self.h + alpha_sz * det.h

        self.age += 1
        self.missing = 0
        self._sync_detection(det.confidence, det.area)

    def mark_missing(self):
        # Drift position by velocity estimate
        self.cx += self.vx
        self.cy += self.vy
        self.missing += 1
        self._sync_detection(self.detection.confidence * 0.92, self.detection.area)

    def _sync_detection(self, confidence: float, area: int):
        iw = max(int(round(self.w)), 1)
        ih = max(int(round(self.h)), 1)
        x = int(round(self.cx - iw / 2))
        y = int(round(self.cy - ih / 2))
        self.detection = Detection(x=x, y=y, w=iw, h=ih, confidence=confidence, area=area)


class ObjectTracker:
    def __init__(self):
        self._tracks: list[TrackedObject] = []
        self._next_id = 0
        self._frame_diag: float = math.hypot(
            config.FRAME_WIDTH, config.FRAME_HEIGHT
        )

    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        # Step 1: greedily match detections to existing tracks
        unmatched_dets = list(range(len(detections)))
        matched_track_ids: set[int] = set()

        # Build score matrix and do greedy assignment (best score first)
        if self._tracks and detections:
            candidates = []
            for ti, track in enumerate(self._tracks):
                for di, det in enumerate(detections):
                    score = _match_score(
                        track.cx, track.cy, track.w, track.h,
                        det, self._frame_diag,
                    )
                    candidates.append((score, ti, di))

            candidates.sort(reverse=True)
            assigned_tracks: set[int] = set()
            assigned_dets: set[int] = set()

            for score, ti, di in candidates:
                if ti in assigned_tracks or di in assigned_dets:
                    continue
                track = self._tracks[ti]
                det = detections[di]

                iou = _iou(
                    int(track.cx - track.w / 2), int(track.cy - track.h / 2),
                    int(track.w), int(track.h),
                    det.x, det.y, det.w, det.h,
                )
                dcx = det.x + det.w / 2
                dcy = det.y + det.h / 2
                dist = math.hypot(dcx - track.cx, dcy - track.cy)

                # Accept if IoU passes OR if close enough in distance
                if iou >= config.TRACK_MIN_IOU or dist <= config.TRACK_MAX_DIST_FRAC * self._frame_diag:
                    track.update(det)
                    assigned_tracks.add(ti)
                    assigned_dets.add(di)
                    matched_track_ids.add(ti)

            unmatched_dets = [i for i in range(len(detections)) if i not in assigned_dets]

        # Step 2: mark unmatched tracks as missing
        for ti, track in enumerate(self._tracks):
            if ti not in matched_track_ids:
                track.mark_missing()

        # Step 3: remove tracks that have been missing too long
        self._tracks = [t for t in self._tracks if t.missing <= config.TRACK_MAX_MISSING_FRAMES]

        # Step 4: spawn new tracks for unmatched detections
        for di in unmatched_dets:
            self._tracks.append(TrackedObject(id=self._next_id, detection=detections[di]))
            self._next_id += 1

        return list(self._tracks)
