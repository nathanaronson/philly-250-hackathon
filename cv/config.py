# All tunable parameters in one place.

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_RATE = 30

# Set to True only on a machine with a GPU or fast CPU (not Pi).
ENABLE_CLIP = False

# --- Background subtraction (MOG2) ---
BG_HISTORY = 300
BG_VAR_THRESHOLD = 50       # pixel variance — higher = less sensitive to shimmer
BG_LEARN_RATE = 0.0005      # post-calibration — very slow so tape stays detected

# --- Gray color filter (duct tape appearance in HSV) ---
GRAY_S_MAX = 70             # max saturation — gray/silver has very low saturation
GRAY_V_MIN = 50             # min brightness — not pitch black
GRAY_V_MAX = 220            # max brightness — not blown-out glare

# --- Contour filtering (at half resolution: 640x360) ---
EDGE_MARGIN = 15            # px — zero out frame border to kill corner artifacts
MIN_CONTOUR_AREA = 200      # px² at half-res (~800 full-res)
MAX_CONTOUR_AREA = 12000    # px² at half-res (~48000 full-res)
MIN_ASPECT_RATIO = 0.35

# --- Single-target tracker ---
TRACK_CONFIRM_FRAMES = 3
TRACK_MAX_MISSING_FRAMES = 15
TRACK_POSITION_SMOOTHING = 0.55
TRACK_SIZE_SMOOTHING = 0.60
TRACK_MAX_MOVE_DIAG = 2.5

# --- Calibration ---
CALIBRATION_SECONDS = 5     # MOG2 learns fast; keep scene empty during this
