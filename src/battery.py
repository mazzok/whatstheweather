"""battery.py — Battery monitoring via INA219 on Seengreat PI Zero UPS HAT (A)."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from ina219 import INA219
except Exception:
    INA219 = None  # type: ignore[assignment,misc]

SHUNT_OHMS = 0.1
MAX_EXPECTED_AMPS = 2.0
I2C_ADDRESS = 0x43

VOLTAGE_EMPTY = 3.0
VOLTAGE_FULL = 4.2

DEFAULT_RECHARGE_PATH = Path.home() / ".weather_recharge"


class BatteryMonitor:
    def __init__(self, recharge_path: Path = DEFAULT_RECHARGE_PATH) -> None:
        self._recharge_path = recharge_path
        try:
            if INA219 is None:
                raise RuntimeError("INA219 library not installed")
            self._ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS, address=I2C_ADDRESS)
            self._ina.configure(self._ina.RANGE_16V)
        except Exception as e:
            logger.debug("INA219 not available: %s", e)
            self._ina = None

    def voltage(self) -> float:
        if self._ina is None:
            return 3.7
        return self._ina.voltage()

    def current(self) -> float:
        if self._ina is None:
            return 0.0
        return self._ina.current()

    def percentage(self) -> int:
        v = self.voltage()
        pct = int((v - VOLTAGE_EMPTY) / (VOLTAGE_FULL - VOLTAGE_EMPTY) * 100)
        return max(0, min(100, pct))

    def is_charging(self) -> bool:
        # Current-based detection doesn't work on this HAT (charge circuit
        # bypasses the INA219 shunt).  Fall back to voltage increase: if the
        # current percentage is higher than the last saved percentage the
        # battery must be charging.
        state = self._read_state()
        return self.percentage() > state["percentage"]

    def _read_state(self) -> dict:
        try:
            data = json.loads(self._recharge_path.read_text())
            return {"date": data["date"], "percentage": data["percentage"]}
        except Exception:
            return {"date": str(date.today()), "percentage": self.percentage()}

    def _write_state(self, recharge_date: str, percentage: int) -> None:
        try:
            self._recharge_path.write_text(
                json.dumps({"date": recharge_date, "percentage": percentage})
            )
        except OSError as e:
            logger.warning("Could not write recharge state: %s", e)

    def get_off_grid_days(self) -> int:
        state = self._read_state()
        current_pct = self.percentage()

        if current_pct > state["percentage"]:
            # Charge increase detected — reset counter
            today_str = str(date.today())
            self._write_state(today_str, current_pct)
            return 0

        # Save current percentage (keep existing date)
        self._write_state(state["date"], current_pct)

        try:
            recharge_date = date.fromisoformat(state["date"])
            return (date.today() - recharge_date).days
        except Exception:
            return 0
