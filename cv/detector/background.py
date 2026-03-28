"""
Background + gray-appearance detector tuned for gray duct tape objects.

Pipeline:
  1. MOG2 gives moving foreground at half resolution for speed.
  2. Gray appearance masks (HSV low saturation + LAB near-neutral chroma)
     indicate tape-like pixels.
  3. Contours are found on foreground, then scored by how gray they are and
     how non-skin they are, so faces/hands are rejected.
  4. If no gray-tape candidate is found, fall back to generic "new object"
     contour detection so any foreign object in frame can still be tracked.
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
        self._open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self._close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        self._target_close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        self._calibration_start = time.monotonic()
        self.debug_mask: np.ndarray | None = None

    @property
    def is_calibrated(self) -> bool:
        return (time.monotonic() - self._calibration_start) >= config.CALIBRATION_SECONDS

    @property
    def calibration_progress(self) -> float:
        elapsed = time.monotonic() - self._calibration_start
        return min(elapsed / config.CALIBRATION_SECONDS, 1.0)

    @staticmethod
    def _clip01(value: float) -> float:
        return max(0.0, min(1.0, value))

    def _gray_and_skin_masks(self, frame_small: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        hsv = cv2.cvtColor(frame_small, cv2.COLOR_BGR2HSV)
        h = hsv[:, :, 0]
        s = hsv[:, :, 1]
        v = hsv[:, :, 2]

        sat_mask = cv2.inRange(s, 0, config.GRAY_S_MAX)
        val_mask = cv2.inRange(v, config.GRAY_V_MIN, config.GRAY_V_MAX)
        gray_hsv = cv2.bitwise_and(sat_mask, val_mask)

        lab = cv2.cvtColor(frame_small, cv2.COLOR_BGR2LAB)
        a = lab[:, :, 1]
        b = lab[:, :, 2]
        neutral_a = cv2.inRange(a, 128 - config.GRAY_AB_MAX, 128 + config.GRAY_AB_MAX)
        neutral_b = cv2.inRange(b, 128 - config.GRAY_AB_MAX, 128 + config.GRAY_AB_MAX)
        gray_lab = cv2.bitwise_and(cv2.bitwise_and(neutral_a, neutral_b), val_mask)

        # OR between HSV-gray and LAB-neutral handles underwater color casts better.
        gray_mask = cv2.bitwise_or(gray_hsv, gray_lab)

        # Broad skin-tone window in HSV; used only as a reject signal.
        skin_h = cv2.inRange(h, 0, 25)
        skin_s = cv2.inRange(s, 30, 220)
        skin_v = cv2.inRange(v, 40, 255)
        skin_mask = cv2.bitwise_and(cv2.bitwise_and(skin_h, skin_s), skin_v)
        return gray_mask, skin_mask

    def _contour_detections(
        self,
        contour_source: np.ndarray,
        gray_mask: np.ndarray,
        skin_mask: np.ndarray,
        require_gray: bool,
        reject_skin: bool,
    ) -> list[Detection]:
        contours, _ = cv2.findContours(
            contour_source, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections: list[Detection] = []
        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if not (config.MIN_CONTOUR_AREA <= area <= config.MAX_CONTOUR_AREA):
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            aspect = min(w, h) / max(w, h) if max(w, h) > 0 else 0.0
            if aspect < config.MIN_ASPECT_RATIO:
                continue

            perimeter = cv2.arcLength(cnt, True)
            circularity = (4 * np.pi * area / (perimeter * perimeter)) if perimeter > 0 else 0.0
            if circularity < config.MIN_CIRCULARITY:
                continue

            contour_mask = np.zeros_like(contour_source)
            cv2.drawContours(contour_mask, [cnt], -1, 255, thickness=-1)
            pixels = float(cv2.countNonZero(contour_mask))
            if pixels <= 0:
                continue

            gray_pixels = cv2.countNonZero(cv2.bitwise_and(gray_mask, contour_mask))
            skin_pixels = cv2.countNonZero(cv2.bitwise_and(skin_mask, contour_mask))
            gray_ratio = gray_pixels / pixels
            skin_ratio = skin_pixels / pixels

            if require_gray and gray_ratio < config.MIN_GRAY_RATIO:
                continue
            if reject_skin and skin_ratio > config.MAX_SKIN_RATIO:
                continue

            fill = area / float(w * h) if w * h > 0 else 0.0
            if fill < config.FALLBACK_MIN_FILL:
                continue

            if require_gray:
                confidence = round(
                    (
                        0.48 * self._clip01(gray_ratio)
                        + 0.18 * self._clip01(aspect)
                        + 0.18 * self._clip01(fill)
                        + 0.16 * self._clip01(circularity)
                    ),
                    3,
                )
            else:
                confidence = round(
                    (
                        0.40 * self._clip01(fill)
                        + 0.30 * self._clip01(aspect)
                        + 0.20 * self._clip01(circularity)
                        + 0.10 * self._clip01(gray_ratio * 2)
                    ),
                    3,
                )
            detections.append(
                Detection(
                    x=x * 2,
                    y=y * 2,
                    w=w * 2,
                    h=h * 2,
                    confidence=confidence,
                    area=int(area * 4),
                )
            )
        return detections

    def process(self, frame: np.ndarray) -> list[Detection]:
        full_h, full_w = frame.shape[:2]
        small = cv2.resize(frame, (full_w // 2, full_h // 2), interpolation=cv2.INTER_AREA)
        small_blur = cv2.GaussianBlur(small, (5, 5), 0)

        if not self.is_calibrated:
            self._mog.apply(small_blur, learningRate=0.05)
            self.debug_mask = np.zeros((full_h, full_w), dtype=np.uint8)
            return []

        fg_raw = self._mog.apply(small_blur, learningRate=config.BG_LEARN_RATE)
        fg_mask = cv2.morphologyEx(fg_raw, cv2.MORPH_OPEN, self._open_kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self._close_kernel)

        margin = config.EDGE_MARGIN
        small_h, small_w = fg_mask.shape[:2]
        fg_mask[:margin, :] = 0
        fg_mask[small_h - margin :, :] = 0
        fg_mask[:, :margin] = 0
        fg_mask[:, small_w - margin :] = 0

        gray_mask, skin_mask = self._gray_and_skin_masks(small)
        target_mask = cv2.bitwise_and(fg_mask, gray_mask)
        target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_CLOSE, self._target_close_kernel)
        debug_small = target_mask if cv2.countNonZero(target_mask) > 0 else fg_mask
        self.debug_mask = cv2.resize(debug_small, (full_w, full_h), interpolation=cv2.INTER_NEAREST)

        detections = self._contour_detections(
            target_mask,
            gray_mask,
            skin_mask,
            require_gray=True,
            reject_skin=True,
        )
        if not detections:
            # Fallback: detect any compact foreign object introduced after calibration.
            detections = self._contour_detections(
                fg_mask,
                gray_mask,
                skin_mask,
                require_gray=False,
                reject_skin=True,
            )

        detections.sort(key=lambda d: (d.confidence, d.area), reverse=True)
        return detections[:3]
