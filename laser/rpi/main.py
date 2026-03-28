import time

import tracker_config as cfg
from servo_control import PanTiltController


def main():
    controller = PanTiltController()
    controller.start()

    # This mode is only for checking the tilt-servo direction.
    # It centers both servos, waits briefly, then nudges tilt a tiny amount.
    print("[rpi] Starting servo direction test")
    print(f"[rpi] Pan GPIO={cfg.PAN_GPIO_PIN}, Tilt GPIO={cfg.TILT_GPIO_PIN}")
    print("[rpi] Centering servos")

    try:
        time.sleep(cfg.TEST_SETTLE_SECONDS)

        print(f"[rpi] Nudging tilt by +{cfg.TILT_TEST_NUDGE_US} us")
        print("[rpi] This is the currently configured UP direction")
        controller.nudge_tilt_up_test()

        # Hold position for a moment so the movement is easy to see.
        time.sleep(cfg.TEST_SETTLE_SECONDS)

    finally:
        controller.cleanup()
        print("[rpi] Stopped")


if __name__ == "__main__":
    main()
