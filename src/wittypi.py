"""wittypi.py — WittyPi 4 L3V7 I2C interface for battery/USB monitoring."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

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

DEFAULT_RECHARGE_PATH = Path.home() / ".weather_recharge"


class WittyPi:
    VOLTAGE_EMPTY = 3.0
    VOLTAGE_FULL = 4.2
    USB_CHARGING_THRESHOLD = 4.0

    def __init__(self, recharge_path: Path = DEFAULT_RECHARGE_PATH) -> None:
        self._recharge_path = recharge_path
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

    def battery_percentage(self) -> int:
        if self._bus is None:
            return 50
        try:
            v_int = self._bus.read_byte_data(I2C_ADDRESS, REG_BATTERY_V_INT)
            v_dec = self._bus.read_byte_data(I2C_ADDRESS, REG_BATTERY_V_DEC)
            v = v_int + v_dec / 100.0
        except Exception:
            return 50
        pct = round((v - self.VOLTAGE_EMPTY) / (self.VOLTAGE_FULL - self.VOLTAGE_EMPTY) * 100)
        return max(0, min(100, pct))

    def is_charging(self) -> bool:
        return self.usb_voltage() > self.USB_CHARGING_THRESHOLD

    def get_off_grid_days(self) -> int:
        current_pct = self.battery_percentage()
        charging = self.is_charging()

        if charging:
            self._write_state(str(date.today()), current_pct)
            return 0

        state = self._read_state()
        self._write_state(state["date"], current_pct)

        try:
            recharge_date = date.fromisoformat(state["date"])
            return (date.today() - recharge_date).days
        except Exception:
            return 0

    def _read_state(self) -> dict:
        try:
            data = json.loads(self._recharge_path.read_text())
            return {"date": data["date"], "percentage": data["percentage"]}
        except Exception:
            return {"date": str(date.today()), "percentage": self.battery_percentage()}

    def _write_state(self, recharge_date: str, percentage: int) -> None:
        try:
            self._recharge_path.write_text(
                json.dumps({"date": recharge_date, "percentage": percentage})
            )
        except OSError as e:
            logger.warning("Could not write recharge state: %s", e)
