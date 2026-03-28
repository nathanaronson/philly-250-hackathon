# All tunable parameters in one place.
# Adjust these if detection is too sensitive or misses objects.

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_RATE = 30

# Background subtractor — how many frames to learn the "empty" background.
# Point the camera at the empty tank for this many frames before dropping anything in.
BG_HISTORY = 60
BG_VAR_THRESHOLD = 40  # higher = less sensitive to noise

# Contour filtering
MIN_CONTOUR_AREA = 500      # pixels^2 — ignore tiny noise blobs
MIN_SOLIDITY = 0.3          # 0-1, how "solid" a blob must be (filters stringy artifacts)

# Confidence display thresholds
HIGH_CONF = 0.70   # green
MED_CONF  = 0.40   # yellow
# below MED_CONF  → red (uncertain detection)

# Calibration: how long to show "calibrating..." overlay (seconds)
CALIBRATION_SECONDS = 3
