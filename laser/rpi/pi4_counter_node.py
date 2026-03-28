from counter_link import run_counter_node


# Update this if your USB radio enumerates differently on the Pi 4.
SERIAL_PORT = "/dev/ttyUSB0"


if __name__ == "__main__":
    run_counter_node(
        port=SERIAL_PORT,
        name="pi4",
        start_value=1,
        initiator=True,
    )
