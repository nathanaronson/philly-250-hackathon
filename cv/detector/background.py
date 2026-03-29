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


def _ensure_onnx(onnx_path: str, imgsz: int) -> str:
    """Return onnx_path if it exists; otherwise export it from the .pt weights."""
    import os
    if os.path.exists(onnx_path):
        return onnx_path

    # Derive the .pt filename (yolov8n.onnx → yolov8n.pt)
    pt_path = onnx_path.replace(".onnx", ".pt")
    print(f"[detector] {onnx_path} not found — exporting from {pt_path} …")
    print("[detector] This takes ~30 s and only runs once.")
    try:
        from ultralytics import YOLO as _YOLO
    except ImportError:
        raise RuntimeError(
            f"{onnx_path} not found and ultralytics is not installed.\n"
            "Either:\n"
            "  1. Run on another machine:  "
            f"python -c \"from ultralytics import YOLO; YOLO('{pt_path}').export(format='onnx', imgsz={imgsz})\"\n"
            "     then copy the .onnx file here.\n"
            "  2. Install ultralytics:  uv add ultralytics torch torchvision"
        )
    _YOLO(pt_path).export(format="onnx", imgsz=imgsz)
    if not os.path.exists(onnx_path):
        raise RuntimeError(f"Export finished but {onnx_path} still not found.")
    print(f"[detector] Exported {onnx_path}")
    return onnx_path


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
            model_path = _ensure_onnx(config.YOLO_MODEL, config.YOLO_IMGSZ)
            print(f"[detector] Loading {model_path} …")
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = config.YOLO_THREADS
            opts.inter_op_num_threads = 1
            BackgroundDetector._session = ort.InferenceSession(
                model_path,
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

    def _infer(self, frame: np.ndarray, fh: int, fw: int):
        """Run one YOLO pass. Returns (x1, y1, w_, h_, conf) arrays or None."""
        sz = config.YOLO_IMGSZ
        resized = cv2.resize(frame, (sz, sz), interpolation=cv2.INTER_LINEAR)
        blob = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)[np.newaxis]

        raw = BackgroundDetector._session.run(None, {self._input_name: blob})[0]
        preds = raw[0].T                          # [N, 84]
        cx, cy, bw, bh = preds[:,0], preds[:,1], preds[:,2], preds[:,3]
        class_scores = preds[:, 4:]               # [N, 80]

        # Confidence = max score across all target classes
        classes = list(config.YOLO_TARGET_CLASSES)
        conf = class_scores[:, classes].max(axis=1)
        keep = conf >= config.YOLO_CONF
        if not np.any(keep):
            return None

        sx, sy = fw / sz, fh / sz
        x1 = (cx[keep] - bw[keep] / 2) * sx
        y1 = (cy[keep] - bh[keep] / 2) * sy
        w_ = bw[keep] * sx
        h_ = bh[keep] * sy
        return x1, y1, w_, h_, conf[keep]

    def process(self, frame: np.ndarray) -> list[Detection]:
        fh, fw = frame.shape[:2]

        # ── Inference (original + optional vertical flip) ─────────────────
        results = [self._infer(frame, fh, fw)]
        if config.YOLO_FLIP_AUGMENT:
            flip_result = self._infer(cv2.flip(frame, 0), fh, fw)
            if flip_result is not None:
                x1f, y1f, wf, hf, cf = flip_result
                # Transform y back to original frame coords
                results.append((x1f, fh - y1f - hf, wf, hf, cf))

        # ── Merge all candidates ──────────────────────────────────────────
        parts = [r for r in results if r is not None]
        if not parts:
            self.debug_mask = np.zeros((fh, fw), dtype=np.uint8)
            return []

        x1 = np.concatenate([p[0] for p in parts])
        y1 = np.concatenate([p[1] for p in parts])
        w_ = np.concatenate([p[2] for p in parts])
        h_ = np.concatenate([p[3] for p in parts])
        conf = np.concatenate([p[4] for p in parts])

        # ── NMS across merged candidates ──────────────────────────────────
        boxes_xywh = np.stack([x1, y1, w_, h_], axis=1).tolist()
        indices = cv2.dnn.NMSBoxes(
            boxes_xywh, conf.tolist(), config.YOLO_CONF, config.YOLO_IOU,
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
                confidence=float(conf[idx]),
                area=ibw * ibh,
            ))
            cv2.rectangle(debug, (bx, by), (bx + ibw, by + ibh), 255, -1)

        self.debug_mask = debug
        return detections
