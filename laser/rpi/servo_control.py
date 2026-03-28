try:
    import RPi.GPIO as GPIO
except ImportError:  # Allows development on non-Pi machines.
    GPIO = None

import tracker_config as cfg


class ServoAxis:
    def __init__(self, pin, invert=False):
        self.pin = pin
        self.invert = invert
        self.pulse_us = cfg.SERVO_CENTER_PULSE_US
        self._pwm = None

    def start(self):
        if GPIO is None:
            return

        GPIO.setup(self.pin, GPIO.OUT)
        self._pwm = GPIO.PWM(self.pin, cfg.SERVO_FREQUENCY_HZ)
        self._pwm.start(self._pulse_to_duty_cycle(self.pulse_us))

    def move_by(self, delta_us):
        if self.invert:
            delta_us = -delta_us

        self.pulse_us += int(delta_us)
        self.pulse_us = max(cfg.SERVO_MIN_PULSE_US, min(cfg.SERVO_MAX_PULSE_US, self.pulse_us))

        if self._pwm is not None:
            self._pwm.ChangeDutyCycle(self._pulse_to_duty_cycle(self.pulse_us))

    def center(self):
        self.pulse_us = cfg.SERVO_CENTER_PULSE_US
        if self._pwm is not None:
            self._pwm.ChangeDutyCycle(self._pulse_to_duty_cycle(self.pulse_us))

    def stop(self):
        if self._pwm is not None:
            self._pwm.stop()
            self._pwm = None

    @staticmethod
    def _pulse_to_duty_cycle(pulse_us):
        period_us = 1000000.0 / cfg.SERVO_FREQUENCY_HZ
        return (pulse_us / period_us) * 100.0


class PanTiltController:
    def __init__(self):
        self.pan = ServoAxis(cfg.PAN_GPIO_PIN, invert=cfg.PAN_INVERT)
        self.tilt = ServoAxis(cfg.TILT_GPIO_PIN, invert=cfg.TILT_INVERT)

    def start(self):
        if GPIO is not None:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

        self.pan.start()
        self.tilt.start()
        self.center()

    def center(self):
        self.pan.center()
        self.tilt.center()

    def nudge_tilt_up_test(self):
        # Positive movement on tilt is currently treated as "up" for this mount.
        self.tilt.move_by(cfg.TILT_TEST_NUDGE_US)

    def update(self, x_error, y_error):
        pan_delta = int(cfg.PAN_STEP_US * x_error)
        tilt_delta = int(cfg.TILT_STEP_US * y_error)

        if abs(x_error) >= cfg.DEADBAND_X:
            self.pan.move_by(pan_delta)

        if abs(y_error) >= cfg.DEADBAND_Y:
            self.tilt.move_by(-tilt_delta)

    def cleanup(self):
        self.pan.stop()
        self.tilt.stop()
        if GPIO is not None:
            GPIO.cleanup()
