from counter_link import run_counter_node


# Update this if your radio is attached to a different serial device on the Pi 5.
SERIAL_PORT = "/dev/serial0"


if __name__ == "__main__":
    run_counter_node(
        port=SERIAL_PORT,
        name="pi5",
        start_value=2,
        initiator=False,
    )
