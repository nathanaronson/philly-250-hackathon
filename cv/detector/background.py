"""
YOLOv8n human detector — pure onnxruntime, no PyTorch.

Uses a pre-exported yolov8n.onnx file so PyTorch is never loaded.
On a Pi 4 this cuts peak RSS from ~500 MB (ultralytics+torch) to ~100 MB.

To export the model (run once on any machine that has ultralytics):

    python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx', imgsz=320)"

Then copy yolov8n.onnx into the cv/ directory.
"""

from dataclasses import dataclass

import cv2
import numpy as np
import onnxruntime as ort

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
    _session: ort.InferenceSession | None = None

    def __init__(self):
        if BackgroundDetector._session is None:
            print(f"[detector] Loading {config.YOLO_MODEL} …")
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = config.YOLO_THREADS
            opts.inter_op_num_threads = 1
            BackgroundDetector._session = ort.InferenceSession(
                config.YOLO_MODEL,
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            inp = BackgroundDetector._session.get_inputs()[0]
            print(f"[detector] Model ready  input={inp.name} shape={inp.shape}")
        self._input_name = BackgroundDetector._session.get_inputs()[0].name
        self.debug_mask: np.ndarray | None = None

    @property
    def is_calibrated(self) -> bool:
        return True

    @property
    def calibration_progress(self) -> float:
        return 1.0

    def process(self, frame: np.ndarray) -> list[Detection]:
        fh, fw = frame.shape[:2]
        sz = config.YOLO_IMGSZ

        # ── Preprocess ────────────────────────────────────────────────────
        resized = cv2.resize(frame, (sz, sz), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)[np.newaxis]   # [1, 3, sz, sz]

        # ── Inference ─────────────────────────────────────────────────────
        raw = BackgroundDetector._session.run(None, {self._input_name: blob})[0]
        # raw: [1, 84, N]  — 84 = 4 box coords + 80 class scores

        preds = raw[0].T   # [N, 84]
        cx, cy, bw, bh = preds[:, 0], preds[:, 1], preds[:, 2], preds[:, 3]
        class_scores = preds[:, 4:]  # [N, 80]

        person_conf = class_scores[:, 0]  # COCO class 0 = person
        keep = person_conf >= config.YOLO_CONF
        if not np.any(keep):
            self.debug_mask = np.zeros((fh, fw), dtype=np.uint8)
            return []

        cx, cy, bw, bh = cx[keep], cy[keep], bw[keep], bh[keep]
        person_conf = person_conf[keep]

        # Scale from model input coords back to original frame coords
        sx, sy = fw / sz, fh / sz
        x1 = (cx - bw / 2) * sx
        y1 = (cy - bh / 2) * sy
        w_  = bw * sx
        h_  = bh * sy

        # ── NMS ───────────────────────────────────────────────────────────
        boxes_xywh = np.stack([x1, y1, w_, h_], axis=1).tolist()
        indices = cv2.dnn.NMSBoxes(
            boxes_xywh,
            person_conf.tolist(),
            config.YOLO_CONF,
            config.YOLO_IOU,
        )

        debug = np.zeros((fh, fw), dtype=np.uint8)
        detections: list[Detection] = []

        for idx in (indices.flatten() if len(indices) else []):
            bx  = max(int(x1[idx]), 0)
            by  = max(int(y1[idx]), 0)
            ibw = max(int(w_[idx]), 1)
            ibh = max(int(h_[idx]), 1)
            detections.append(Detection(
                x=bx, y=by, w=ibw, h=ibh,
                confidence=float(person_conf[idx]),
                area=ibw * ibh,
            ))
            cv2.rectangle(debug, (bx, by), (bx + ibw, by + ibh), 255, -1)

        self.debug_mask = debug
        return detections
