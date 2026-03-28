"""
Background-subtraction + gray-color detector for duct-tape-roll detection.

Combines MOG2 (what changed?) with an HSV gray filter (what looks like duct tape?)
so only NEW GRAY objects trigger a detection. Processes at half resolution for speed.
"""

from dataclasses import dataclass
import time

import cv2
import numpy as np

import config


@dataclass
class Detection:
    x: int
    y: int
    w: int
    h: int
    confidence: float
    area: int


class BackgroundDetector:
    def __init__(self):
        self._mog = cv2.createBackgroundSubtractorMOG2(
            history=config.BG_HISTORY,
            varThreshold=config.BG_VAR_THRESHOLD,
            detectShadows=False,
        )
        self._open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
        self._calibration_start = time.monotonic()
        self.debug_mask: np.ndarray | None = None

    @property
    def is_calibrated(self) -> bool:
        return (time.monotonic() - self._calibration_start) >= config.CALIBRATION_SECONDS

    @property
    def calibration_progress(self) -> float:
        elapsed = time.monotonic() - self._calibration_start
        return min(elapsed / config.CALIBRATION_SECONDS, 1.0)

    def process(self, frame: np.ndarray) -> list[Detection]:
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
        small_blur = cv2.GaussianBlur(small, (5, 5), 0)

        if not self.is_calibrated:
            self._mog.apply(small_blur, learningRate=0.05)
            self.debug_mask = np.zeros((h, w), dtype=np.uint8)
            return []

        # What changed from background
        fg_mask = self._mog.apply(small_blur, learningRate=config.BG_LEARN_RATE)

        # What looks gray (duct tape color) — low saturation, medium brightness
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        gray_mask = cv2.inRange(
            hsv,
            (0, 0, config.GRAY_V_MIN),
            (180, config.GRAY_S_MAX, config.GRAY_V_MAX),
        )

        # Only keep pixels that are BOTH new AND gray
        combined = cv2.bitwise_and(fg_mask, gray_mask)

        # Cleanup
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, self._open_kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, self._close_kernel)

        # Kill edge artifacts
        m = config.EDGE_MARGIN
        sh, sw = combined.shape[:2]
        combined[:m, :] = 0
        combined[sh - m:, :] = 0
        combined[:, :m] = 0
        combined[:, sw - m:] = 0

        self.debug_mask = cv2.resize(combined, (w, h), interpolation=cv2.INTER_NEAREST)

        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections: list[Detection] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (config.MIN_CONTOUR_AREA <= area <= config.MAX_CONTOUR_AREA):
                continue

            bx, by, bw, bh = cv2.boundingRect(cnt)
            aspect = min(bw, bh) / max(bw, bh) if max(bw, bh) > 0 else 0
            if aspect < config.MIN_ASPECT_RATIO:
                continue

            fill = area / (bw * bh) if bw * bh > 0 else 0
            if fill < 0.20:
                continue

            confidence = round(0.5 * fill + 0.5 * aspect, 3)

            # Scale back to full resolution
            detections.append(Detection(
                x=bx * 2, y=by * 2,
                w=bw * 2, h=bh * 2,
                confidence=confidence,
                area=int(area * 4),
            ))

        detections.sort(key=lambda d: d.area, reverse=True)
        return detections[:3]
