"""
YOLOv8n human detector.

Runs YOLOv8n on each frame filtered to COCO class 0 (person).
Exposes the same interface as the old background-subtraction detector
so the tracker, display, and Flask app need no changes.
"""

from dataclasses import dataclass

import cv2
import numpy as np
from ultralytics import YOLO

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
    # Shared model instance — loaded once, reused across resets.
    _model: YOLO | None = None

    def __init__(self):
        if BackgroundDetector._model is None:
            print(f"[detector] Loading {config.YOLO_MODEL} …")
            model = YOLO(config.YOLO_MODEL, task="detect")
            # Force CPU — Pi has no CUDA/MPS; explicit device avoids torch
            # trying to probe accelerators and potentially segfaulting.
            model.to("cpu")
            BackgroundDetector._model = model
            print("[detector] Model ready")
        self.debug_mask: np.ndarray | None = None

    # No calibration phase for YOLO — always ready.
    @property
    def is_calibrated(self) -> bool:
        return True

    @property
    def calibration_progress(self) -> float:
        return 1.0

    def process(self, frame: np.ndarray) -> list[Detection]:
        h, w = frame.shape[:2]

        results = BackgroundDetector._model.predict(
            frame,
            classes=[0],            # person only
            conf=config.YOLO_CONF,
            iou=config.YOLO_IOU,
            imgsz=config.YOLO_IMGSZ,
            device="cpu",
            verbose=False,
        )

        detections: list[Detection] = []
        debug = np.zeros((h, w), dtype=np.uint8)

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                conf = float(box.conf[0])
                bw = max(x2 - x1, 1)
                bh = max(y2 - y1, 1)
                detections.append(Detection(
                    x=x1, y=y1, w=bw, h=bh,
                    confidence=conf,
                    area=bw * bh,
                ))
                cv2.rectangle(debug, (x1, y1), (x2, y2), 255, -1)

        self.debug_mask = debug
        return detections
