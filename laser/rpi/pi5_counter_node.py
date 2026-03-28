import glob

from counter_link import run_counter_node


def _detect_usb_serial_port() -> str:
    candidates = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    if not candidates:
        raise RuntimeError("No USB serial radio found at /dev/ttyUSB* or /dev/ttyACM*")

    return candidates[0]


if __name__ == "__main__":
    run_counter_node(
        port=_detect_usb_serial_port(),
        name="pi5",
        start_value=2,
        initiator=False,
    )
