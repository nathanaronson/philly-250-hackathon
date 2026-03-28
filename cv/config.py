# All tunable parameters in one place.

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_RATE = 24
STREAM_JPEG_QUALITY = 60

ENABLE_CLIP = False

# --- Raspberry Pi camera stability ---
PI_STABILIZE_CONTROLS = True
PI_AF_MODE = "auto"
PI_AWB_MODE = "auto"
PI_DENOISE_MODE = "cdn_off"

# --- YOLOv8 ---
YOLO_MODEL = "yolov8n.pt"   # downloads automatically on first run
YOLO_CONF = 0.45            # minimum detection confidence
YOLO_IOU = 0.45             # NMS IoU threshold
YOLO_IMGSZ = 640            # inference resolution (smaller = faster on Pi)

# --- Multi-object tracker ---
TRACK_CONFIRM_FRAMES = 2
TRACK_MAX_MISSING_FRAMES = 20
TRACK_MAX_DIST_FRAC = 0.35
TRACK_MIN_IOU = 0.05
TRACK_POSITION_SMOOTHING = 0.6
TRACK_SIZE_SMOOTHING = 0.7
