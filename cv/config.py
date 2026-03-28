# All tunable parameters in one place.

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_RATE = 30

# Set to True only on a machine with a GPU or fast CPU (not Pi).
ENABLE_CLIP = False

# --- Raspberry Pi camera stability ---
# Continuous AF and auto controls can make video "breathe"/jitter on Pi.
PI_STABILIZE_CONTROLS = True
PI_AF_MODE = "auto"          # "auto" does a startup focus sweep then holds more stable than continuous
PI_AWB_MODE = "auto"
PI_DENOISE_MODE = "cdn_off"  # disable temporal denoise shimmer

# --- Background subtraction (MOG2) ---
BG_HISTORY = 300
BG_VAR_THRESHOLD = 50       # pixel variance — higher = less sensitive to shimmer
BG_LEARN_RATE = 0.0002      # post-calibration — slower so target is not absorbed

# --- Gray color filter (duct tape appearance in HSV) ---
GRAY_S_MAX = 95             # max saturation — gray/silver has low saturation
GRAY_V_MIN = 50             # min brightness — not pitch black
GRAY_V_MAX = 245            # max brightness — allow specular highlights on tape
GRAY_AB_MAX = 26            # LAB chroma tolerance from neutral gray (128,128)
MIN_GRAY_RATIO = 0.28       # fraction of contour pixels that must be tape-like gray
MAX_SKIN_RATIO = 0.22       # reject face/skin false positives

# --- Contour filtering (at half resolution: 640x360) ---
EDGE_MARGIN = 15            # px — zero out frame border to kill corner artifacts
MIN_CONTOUR_AREA = 200      # px² at half-res (~800 full-res)
MAX_CONTOUR_AREA = 12000    # px² at half-res (~48000 full-res)
MIN_ASPECT_RATIO = 0.35
MIN_CIRCULARITY = 0.08

# --- Single-target tracker ---
TRACK_CONFIRM_FRAMES = 3
TRACK_MAX_MISSING_FRAMES = 15
TRACK_POSITION_SMOOTHING = 0.72
TRACK_SIZE_SMOOTHING = 0.75
TRACK_MAX_MOVE_DIAG = 2.5

# --- Calibration ---
CALIBRATION_SECONDS = 8     # give MOG2 a cleaner baseline on Pi
