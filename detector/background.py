"""
Background subtraction detector using OpenCV MOG2.

How it works:
  1. For the first N frames (BG_HISTORY in config), the subtractor learns
     what "empty tank" looks like — this is the calibration phase.
  2. After calibration, the background model is frozen (learningRate=0) so
     stationary objects stay detected indefinitely rather than being absorbed.
  3. Foreground pixels are grouped into contours (blobs). Small/spindly blobs
     are filtered out. Remaining blobs are treated as detected objects.
  4. Each detection gets a confidence score derived from blob solidity and size.
"""

import cv2
import numpy as np
import config
from dataclasses import dataclass


@dataclass
class Detection:
    x: int
    y: int
    w: int
    h: int
    confidence: float   # 0.0 – 1.0
    area: int


class BackgroundDetector:
    def __init__(self):
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=config.BG_HISTORY,
            varThreshold=config.BG_VAR_THRESHOLD,
            detectShadows=False,
        )
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._frame_count = 0
        self._calibration_frames = int(config.BG_HISTORY * config.FRAME_RATE * config.CALIBRATION_SECONDS / config.BG_HISTORY)

    @property
    def is_calibrated(self) -> bool:
        return self._frame_count >= self._calibration_frames

    @property
    def calibration_progress(self) -> float:
        """0.0 → 1.0 progress through calibration."""
        return min(self._frame_count / self._calibration_frames, 1.0)

    def process(self, frame: np.ndarray) -> list[Detection]:
        """
        Feed a frame through the detector.
        Returns a list of Detections (empty list during calibration or when nothing found).
        """
        # During calibration: learn freely (learningRate=-1 = automatic).
        # After calibration: freeze the model so stationary objects stay detected.
        learning_rate = -1 if not self.is_calibrated else 0
        fg_mask = self._subtractor.apply(frame, learningRate=learning_rate)
        self._frame_count += 1

        # Clean up noise: remove small speckles, then fill gaps
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self._kernel)

        if not self.is_calibrated:
            return []

        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections: list[Detection] = []
        for cnt in contours:
            area = int(cv2.contourArea(cnt))
            if area < config.MIN_CONTOUR_AREA:
                continue

            hull_area = cv2.contourArea(cv2.convexHull(cnt))
            if hull_area == 0:
                continue
            solidity = area / hull_area
            if solidity < config.MIN_SOLIDITY:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            confidence = _compute_confidence(area, solidity)
            detections.append(Detection(x=x, y=y, w=w, h=h, confidence=confidence, area=area))

        # Sort highest confidence first
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections


def _compute_confidence(area: int, solidity: float) -> float:
    """
    Heuristic confidence score based on blob area and solidity.
    - Larger blobs → more confident (capped at a reasonable size)
    - More solid (compact) blobs → more confident
    Both factors normalized to [0, 1] and averaged.
    """
    MAX_AREA = 20_000
    area_score = min(area / MAX_AREA, 1.0)
    solidity_score = min(solidity, 1.0)
    return round((area_score + solidity_score) / 2, 3)
