# All tunable parameters in one place.
# Adjust these if detection is too sensitive or misses objects.

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_RATE = 30

# Set to True only on a machine with a GPU or fast CPU (not Pi).
# When False, every confirmed detection is treated as a mine-like object.
ENABLE_CLIP = False

# Background subtractor — how many frames to learn the "empty" background.
# Point the camera at the empty seafloor for this many frames before any objects enter.
BG_HISTORY = 90
BG_VAR_THRESHOLD = 25  # lower = more sensitive; underwater has less ambient motion than air

# Contour filtering — tuned for mine-sized objects, not people
MIN_CONTOUR_AREA = 600      # pixels^2 — mines can be relatively small in frame
MIN_SOLIDITY = 0.5          # mines are compact; reject jagged noise blobs
MIN_ASPECT_RATIO = 0.10     # min(w,h)/max(w,h) — relaxed for testing with phone/printed images
MIN_CIRCULARITY = 0.05      # 4π·area/perimeter² — relaxed for testing with phone/printed images

# Blob merging — small radius keeps discrete mine shapes separate.
# Unlike people (many disconnected blobs), mines are already compact.
MERGE_RADIUS = 10

# Confidence display thresholds
HIGH_CONF = 0.70   # green
MED_CONF  = 0.40   # yellow
# below MED_CONF  → red (uncertain detection)

# Calibration: how long to learn the "empty seafloor" background (seconds)
CALIBRATION_SECONDS = 12  # keep scene still during this window
