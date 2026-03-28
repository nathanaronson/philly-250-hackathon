PAN_GPIO_PIN = 18
TILT_GPIO_PIN = 19

SERVO_FREQUENCY_HZ = 50
SERVO_MIN_PULSE_US = 900
SERVO_CENTER_PULSE_US = 1500
SERVO_MAX_PULSE_US = 2100

# These are positional servos, so the tracker keeps updating the
# commanded pulse width to hold the camera at a target angle.

# Flip these if the mount moves opposite to the requested direction.
PAN_INVERT = False
TILT_INVERT = False

# Tracking behavior.
DEADBAND_X = 0.08
DEADBAND_Y = 0.08
PAN_STEP_US = 180
TILT_STEP_US = 180

# Bright red-light detection tuning.
MIN_RED_VALUE = 170
MIN_RED_EXCESS = 35
THRESHOLD_MARGIN = 20
MIN_BLOB_AREA = 16
BLUR_KERNEL = 9

SHOW_WINDOW = True
WINDOW_NAME = "Pi Light Tracker"
