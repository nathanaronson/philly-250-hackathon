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

# --- YOLOv8 (onnxruntime) ---
# Export once on any machine with ultralytics installed:
#   python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx', imgsz=320)"
# Then copy yolov8n.onnx into the cv/ directory.
YOLO_MODEL        = "yolov8n.onnx"
YOLO_CONF         = 0.20   # low threshold for poor camera quality
YOLO_IOU          = 0.45   # NMS IoU threshold
YOLO_IMGSZ        = 320    # must match the size used during export
YOLO_THREADS      = 4      # onnxruntime intra-op threads (Pi 4 has 4 cores)
# COCO classes to treat as a mine target (any match triggers detection).
# 39 = bottle, 41 = cup  — combined catches more can orientations in one pass
# 0  = person            — useful for indoor testing without a can
YOLO_TARGET_CLASSES = [48, 32, 0]  # 48 = orange, 32 = sports ball, 0 = person
# Run a second inference on a vertically-flipped frame and merge results.
# Directly fixes upside-down can detection. Costs one extra inference per frame.
YOLO_FLIP_AUGMENT = True

# --- Multi-object tracker ---
TRACK_CONFIRM_FRAMES    = 2
TRACK_MAX_MISSING_FRAMES = 20
TRACK_MAX_DIST_FRAC     = 0.35
TRACK_MIN_IOU           = 0.05
TRACK_POSITION_SMOOTHING = 0.6
TRACK_SIZE_SMOOTHING    = 0.7

# --- Camera geometry for mine geo-positioning ---
# Measure CAMERA_HEIGHT_M from the lens to the water surface.
# CAMERA_MOUNT_PITCH_DEG is the physical tilt of the camera below horizontal
# (e.g. -45 means pointing 45° downward); IMU pitch is added on top of this.
# Pi Camera v2 FoVs; adjust if using a different lens.
CAMERA_HEIGHT_M        =  0.5    # metres above water surface
CAMERA_HFOV_DEG        = 62.2    # horizontal field of view
CAMERA_VFOV_DEG        = 48.8    # vertical field of view
CAMERA_MOUNT_PITCH_DEG = -45.0   # static camera tilt from level (negative = down)
CAMERA_MOUNT_ROLL_DEG  =  0.0    # static camera roll from level
