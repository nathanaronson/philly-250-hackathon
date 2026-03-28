from counter_link import run_counter_node


# Raspberry Pi 4 now uses the wired UART radio.
SERIAL_PORT = "/dev/serial0"


if __name__ == "__main__":
    run_counter_node(
        port=SERIAL_PORT,
        name="pi4",
        start_value=1,
        initiator=True,
    )
