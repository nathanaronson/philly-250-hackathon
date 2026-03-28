# All tunable parameters in one place.
# Adjust these if detection is too sensitive or misses objects.

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_RATE = 30

# Set to True only on a machine with a GPU or fast CPU (not Pi).
# When False, every confirmed detection is treated as a mine-like object.
ENABLE_CLIP = False

# Background subtractor — how many frames to learn the "empty" background.
# Point the camera at the empty tank for this many frames before adding any objects.
BG_HISTORY = 120
BG_VAR_THRESHOLD = 100  # high — ignores water shimmer, lighting drift, camera noise

# Contour filtering — sized for a solid object (aluminum ball) in a 1280x720 frame.
# A ball ~10cm across in a ~60cm-wide tank ≈ 11 000 px² at this resolution.
MIN_CONTOUR_AREA  = 4000   # px² — rejects water ripples and small noise blobs
MAX_CONTOUR_AREA  = 60000  # px² — rejects hands/arms/bodies once merged
MIN_SOLIDITY      = 0.50   # rejects diffuse water shimmer; passes rings/hollow objects
MIN_ASPECT_RATIO  = 0.20   # not a thin streak/reflection — passes phones, balls, rocks
MIN_CIRCULARITY   = 0.10   # minimal shape check — solidity does the real filtering

# Blob merging — close small gaps within a single object body
MERGE_RADIUS = 35  # large enough to fuse hand+arm fragments into one blob

# Confidence display thresholds
HIGH_CONF = 0.70   # green
MED_CONF  = 0.40   # yellow

# Calibration: how long to learn the background (seconds) — keep tank empty
CALIBRATION_SECONDS = 15
