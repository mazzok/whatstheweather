"""wittypi.py — WittyPi 4 L3V7 I2C interface for battery/USB monitoring."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

I2C_ADDRESS = 0x08
I2C_BUS = 1

REG_BATTERY_V_INT = 0x01
REG_BATTERY_V_DEC = 0x02
REG_USB_V_INT = 0x03
REG_USB_V_DEC = 0x04

try:
    from smbus2 import SMBus
except ImportError:
    SMBus = None  # type: ignore[assignment,misc]


class WittyPi:
    def __init__(self) -> None:
        self._bus = None
        try:
            if SMBus is None:
                raise RuntimeError("smbus2 not installed")
            self._bus = SMBus(I2C_BUS)
        except Exception as e:
            logger.debug("WittyPi I2C not available: %s", e)

    def _read_voltage(self, reg_int: int, reg_dec: int, fallback: float) -> float:
        if self._bus is None:
            return fallback
        try:
            v_int = self._bus.read_byte_data(I2C_ADDRESS, reg_int)
            v_dec = self._bus.read_byte_data(I2C_ADDRESS, reg_dec)
            return v_int + v_dec / 100.0
        except Exception as e:
            logger.debug("I2C read error (reg 0x%02x): %s", reg_int, e)
            return fallback

    def battery_voltage(self) -> float:
        return self._read_voltage(REG_BATTERY_V_INT, REG_BATTERY_V_DEC, fallback=3.7)

    def usb_voltage(self) -> float:
        return self._read_voltage(REG_USB_V_INT, REG_USB_V_DEC, fallback=0.0)
