"""
Background subtraction detector using OpenCV MOG2, tuned for underwater mine detection.

How it works:
  1. Each frame is preprocessed with CLAHE (contrast-limited adaptive histogram
     equalization) to compensate for uneven underwater lighting and colour cast.
  2. For the first N frames (BG_HISTORY in config), the subtractor learns
     what the "empty seafloor" looks like — this is the calibration phase.
  3. After calibration, the background model is frozen (learningRate=0) so
     stationary objects stay detected indefinitely rather than being absorbed.
  4. Foreground pixels are grouped into contours. Blobs are filtered on:
       - minimum area          (ignore sensor noise)
       - solidity              (reject jagged / coral-shaped blobs)
       - aspect ratio          (reject thin fish / cables)
       - circularity           (mines are round; rejects elongated shapes)
  5. Each detection gets a confidence score from area, solidity, and circularity.
"""

import math
import time
import cv2
import numpy as np
import config
from dataclasses import dataclass

# CLAHE instance — shared across frames, cheap to reuse
_clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))


def _preprocess_underwater(frame: np.ndarray) -> np.ndarray:
    """
    Apply CLAHE in LAB colour space.
    - Only the L (lightness) channel is equalised, so colours are preserved.
    - Compensates for murky water, backscatter, and non-uniform illumination.
    """
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = _clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


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
        # Larger kernel: aggressively suppress water shimmer / speckle noise
        self._noise_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        # Merge kernel: close small gaps within a single mine body
        r = config.MERGE_RADIUS
        self._merge_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r * 2, r * 2))
        self._calibration_start = time.monotonic()
        self.debug_mask: np.ndarray | None = None  # exposed for /debug endpoint

    @property
    def is_calibrated(self) -> bool:
        return (time.monotonic() - self._calibration_start) >= config.CALIBRATION_SECONDS

    @property
    def calibration_progress(self) -> float:
        """0.0 → 1.0 progress through calibration."""
        elapsed = time.monotonic() - self._calibration_start
        return min(elapsed / config.CALIBRATION_SECONDS, 1.0)

    def process(self, frame: np.ndarray) -> list[Detection]:
        """
        Feed a frame through the detector.
        Returns a list of Detections (empty list during calibration or when nothing found).
        """
        frame = _preprocess_underwater(frame)

        # During calibration: learn freely (learningRate=-1 = automatic).
        # After calibration: freeze the model so stationary objects stay detected.
        learning_rate = -1 if not self.is_calibrated else 0
        fg_mask = self._subtractor.apply(frame, learningRate=learning_rate)

        # Remove speckle noise, then close small gaps within blobs
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._noise_kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self._merge_kernel)
        self.debug_mask = fg_mask.copy()

        if not self.is_calibrated:
            return []

        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections: list[Detection] = []
        for cnt in contours:
            area = int(cv2.contourArea(cnt))
            if area < config.MIN_CONTOUR_AREA or area > config.MAX_CONTOUR_AREA:
                continue

            # Solidity: how much of the convex hull is filled (mines are solid)
            hull_area = cv2.contourArea(cv2.convexHull(cnt))
            if hull_area == 0:
                continue
            solidity = area / hull_area
            if solidity < config.MIN_SOLIDITY:
                continue

            # Aspect ratio: mines are roughly round, not wires or fish tails
            x, y, w, h = cv2.boundingRect(cnt)
            aspect = min(w, h) / max(w, h) if max(w, h) > 0 else 0.0
            if aspect < config.MIN_ASPECT_RATIO:
                continue

            # Circularity: 4π·area / perimeter² — perfect circle = 1.0
            perimeter = cv2.arcLength(cnt, True)
            circularity = (4 * math.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0
            if circularity < config.MIN_CIRCULARITY:
                continue

            confidence = _compute_confidence(area, solidity, circularity)
            detections.append(Detection(x=x, y=y, w=w, h=h, confidence=confidence, area=area))

        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections


def _compute_confidence(area: int, solidity: float, circularity: float) -> float:
    """
    Heuristic confidence score for mine-like blobs.
    - Larger blobs → more confident (capped at a reference mine size)
    - High solidity → compact, not a coral fragment
    - High circularity → round, consistent with spherical / cylindrical mines
    All three factors averaged into [0, 1].
    """
    MAX_AREA = 12_000   # ~110×110 px — large mine at close range
    area_score = min(area / MAX_AREA, 1.0)
    solidity_score = min(solidity, 1.0)
    circularity_score = min(circularity, 1.0)
    return round((area_score + solidity_score + circularity_score) / 3, 3)
