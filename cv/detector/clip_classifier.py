"""
CLIP zero-shot mine classifier.

Crops the detected ROI from the frame and asks CLIP:
"Which of these descriptions fits best?"

No training data required — CLIP understands visual concepts from text.
Runs once per newly-confirmed object (not every frame), so it doesn't
bottleneck the capture loop.
"""

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from transformers import CLIPImageProcessor, CLIPModel, CLIPTokenizerFast

# These labels define what CLIP compares against.
# More specific mine descriptions help CLIP distinguish from similar-looking objects.
_LABELS = [
    "an underwater sea mine, spherical with metal spikes",
    "a fish swimming underwater",
    "a rock or coral on the seafloor",
    "marine debris or trash underwater",
    "an underwater creature or animal",
    "sand or seafloor sediment",
]

# Index 0 is the mine label — score returned is P(mine)
_MINE_IDX = 0

# Minimum CLIP probability to treat a detection as a mine.
# Lower = more sensitive (more false positives); higher = more strict.
MINE_THRESHOLD = 0.30


_MODEL_ID = "openai/clip-vit-base-patch32"


class CLIPClassifier:
    def __init__(self):
        print("[CLIP] Loading model (one-time)...")
        self._model = CLIPModel.from_pretrained(_MODEL_ID)
        self._tokenizer = CLIPTokenizerFast.from_pretrained(_MODEL_ID)
        self._img_processor = CLIPImageProcessor.from_pretrained(_MODEL_ID)
        self._model.eval()

        # Pre-encode text labels — only needs to happen once at startup
        with torch.no_grad():
            text_inputs = self._tokenizer(_LABELS, return_tensors="pt", padding=True)
            text_out = self._model.text_model(**text_inputs)
            text_feats = self._model.text_projection(text_out.pooler_output)
            self._text_features = F.normalize(text_feats, dim=-1)

        print("[CLIP] Ready.")

    def score(self, frame: np.ndarray, x: int, y: int, w: int, h: int) -> float:
        """
        Returns P(mine) in [0, 1] for the given bounding box in `frame`.
        Frame is expected in BGR format (as returned by OpenCV).
        """
        # Add padding around the ROI so CLIP has context
        pad = max(w, h) // 4
        fh, fw = frame.shape[:2]
        x1 = max(x - pad, 0)
        y1 = max(y - pad, 0)
        x2 = min(x + w + pad, fw)
        y2 = min(y + h + pad, fh)

        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return 0.0

        # Upscale small ROIs — CLIP works better with larger images
        rh, rw = roi.shape[:2]
        if rw < 112 or rh < 112:
            scale = max(112 / rw, 112 / rh)
            roi = cv2.resize(roi, (int(rw * scale), int(rh * scale)), interpolation=cv2.INTER_LINEAR)

        pil_img = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))

        with torch.no_grad():
            img_inputs = self._img_processor(images=pil_img, return_tensors="pt")
            vision_out = self._model.vision_model(**img_inputs)
            img_feats = self._model.visual_projection(vision_out.pooler_output)
            img_feats = F.normalize(img_feats, dim=-1)

            # Cosine similarity → softmax → probabilities
            logits = (img_feats @ self._text_features.T) * self._model.logit_scale.exp()
            probs = logits.softmax(dim=-1)[0]

        return float(probs[_MINE_IDX])
