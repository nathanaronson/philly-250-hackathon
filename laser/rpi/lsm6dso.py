from __future__ import annotations

from dataclasses import dataclass

from smbus2 import SMBus


WHO_AM_I_REGISTER = 0x0F
WHO_AM_I_VALUE = 0x6C

CTRL1_XL = 0x10
CTRL2_G = 0x11

OUT_TEMP_L = 0x20

LSM6DSO_ADDRESSES = (0x6A, 0x6B)

# 104 Hz, +/-2 g
CTRL1_XL_VALUE = 0x40

# 104 Hz, 250 dps
CTRL2_G_VALUE = 0x40

ACCEL_SENSITIVITY_MG_PER_LSB = 0.061
GYRO_SENSITIVITY_MDPS_PER_LSB = 8.75
TEMP_SENSITIVITY_C_PER_LSB = 1.0 / 256.0
TEMP_OFFSET_C = 25.0


@dataclass
class ImuSample:
    accel_x_mg: int
    accel_y_mg: int
    accel_z_mg: int
    gyro_x_mdps: int
    gyro_y_mdps: int
    gyro_z_mdps: int
    temperature_centi_c: int


class LSM6DSO:
    def __init__(self, bus_id: int = 1, address: int | None = None) -> None:
        self.bus = SMBus(bus_id)
        self.address = address if address is not None else self._detect_address()
        self._configure()

    def _detect_address(self) -> int:
        for address in LSM6DSO_ADDRESSES:
            try:
                value = self.bus.read_byte_data(address, WHO_AM_I_REGISTER)
            except OSError:
                continue

            if value == WHO_AM_I_VALUE:
                return address

        raise RuntimeError("Could not find LSM6DSO at 0x6A or 0x6B")

    def _configure(self) -> None:
        self.bus.write_byte_data(self.address, CTRL1_XL, CTRL1_XL_VALUE)
        self.bus.write_byte_data(self.address, CTRL2_G, CTRL2_G_VALUE)

    def read_sample(self) -> ImuSample:
        raw = self.bus.read_i2c_block_data(self.address, OUT_TEMP_L, 14)

        temperature_raw = _to_int16(raw[0], raw[1])
        gyro_x_raw = _to_int16(raw[2], raw[3])
        gyro_y_raw = _to_int16(raw[4], raw[5])
        gyro_z_raw = _to_int16(raw[6], raw[7])
        accel_x_raw = _to_int16(raw[8], raw[9])
        accel_y_raw = _to_int16(raw[10], raw[11])
        accel_z_raw = _to_int16(raw[12], raw[13])

        return ImuSample(
            accel_x_mg=int(accel_x_raw * ACCEL_SENSITIVITY_MG_PER_LSB),
            accel_y_mg=int(accel_y_raw * ACCEL_SENSITIVITY_MG_PER_LSB),
            accel_z_mg=int(accel_z_raw * ACCEL_SENSITIVITY_MG_PER_LSB),
            gyro_x_mdps=int(gyro_x_raw * GYRO_SENSITIVITY_MDPS_PER_LSB),
            gyro_y_mdps=int(gyro_y_raw * GYRO_SENSITIVITY_MDPS_PER_LSB),
            gyro_z_mdps=int(gyro_z_raw * GYRO_SENSITIVITY_MDPS_PER_LSB),
            temperature_centi_c=int(
                (TEMP_OFFSET_C + (temperature_raw * TEMP_SENSITIVITY_C_PER_LSB)) * 100.0
            ),
        )

    def close(self) -> None:
        self.bus.close()


def _to_int16(low_byte: int, high_byte: int) -> int:
    value = (high_byte << 8) | low_byte
    if value & 0x8000:
        value -= 0x10000
    return value
