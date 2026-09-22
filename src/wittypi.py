"""wittypi.py — WittyPi 4 L3V7 I2C interface for battery/USB monitoring."""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

I2C_ADDRESS = 0x08
I2C_BUS = 1

REG_BATTERY_V_INT = 0x01
REG_BATTERY_V_DEC = 0x02
# Registers 0x03/0x04 report Vout (WittyPi's regulated 5V rail to the Pi), not the raw
# external USB input — Vout stays ~5.2V whenever the Pi is powered, from either source.
REG_USB_V_INT = 0x03
REG_USB_V_DEC = 0x04

# Power source as classified by WittyPi's MCU (I2C_POWER_MODE in ~/wittypi/utilities.sh):
# 0 = powered from the external Vin/USB-C input, non-zero = running off the battery.
# Verified on hardware by diffing the full register block plugged vs. unplugged: this
# register is the only clean binary discriminator between the two states.
#
# Note this reports the power *source*, not charge activity — it stays 0 once a full
# battery stops drawing current, which is what we want: the Pi should stay awake for as
# long as USB-C is connected. GPIO 5 (CHRG_PIN), which wittyPi.sh uses for true charge
# detection, reads a constant 1 on this unit regardless of input and cannot be used.
REG_POWER_MODE = 0x07
POWER_MODE_EXTERNAL = 0x00

# LiPo discharge is strongly nonlinear; a straight-line voltage-to-percent mapping
# overestimates charge by ~38 percentage points near empty. These control points
# (descending by voltage) come from a real discharge curve for this cell chemistry.
_SOC_CURVE: list[tuple[float, int]] = [
    (4.20, 100), (4.06, 90), (3.98, 80), (3.92, 70), (3.87, 60),
    (3.82, 50), (3.79, 40), (3.77, 30), (3.74, 20), (3.68, 10), (3.45, 0),
]


def _voltage_to_percent(v: float) -> int:
    """Map a battery voltage to a state-of-charge percentage via piecewise-linear
    interpolation over _SOC_CURVE. Pure and stateless — no I2C, no hardware needed."""
    if v >= _SOC_CURVE[0][0]:
        return 100
    if v <= _SOC_CURVE[-1][0]:
        return 0
    for (v_hi, p_hi), (v_lo, p_lo) in zip(_SOC_CURVE, _SOC_CURVE[1:]):
        if v_lo <= v <= v_hi:
            frac = (v - v_lo) / (v_hi - v_lo)
            return round(p_lo + frac * (p_hi - p_lo))
    return 0  # unreachable given the bounds checks above


try:
    from smbus2 import SMBus
except ImportError:
    SMBus = None  # type: ignore[assignment,misc]

DEFAULT_RECHARGE_PATH = Path.home() / ".weather_recharge"
DEFAULT_BOOT_LOG_PATH = Path.home() / ".weather_battery_log.csv"
DEFAULT_WITTYPI_DIR = Path.home() / "wittypi"

# Deployed schedule filenames under <wittypi_dir>/schedules/ (see README setup step 9).
# SCHEDULE_NORMAL_NAME enforces WittyPi's own hard shutdown after the ON window — the
# safety backstop for battery-only operation. SCHEDULE_CHARGING_NAME uses the WAIT
# modifier so WittyPi does NOT auto-shutdown; the app stays awake and is responsible
# for calling shutdown itself once charging stops (see _run_charging_mode in main.py).
SCHEDULE_NORMAL_NAME = "weatherpi.wpi"
SCHEDULE_CHARGING_NAME = "weatherpi-charging.wpi"


class WittyPi:
    def __init__(
        self,
        recharge_path: Path = DEFAULT_RECHARGE_PATH,
        boot_log_path: Path = DEFAULT_BOOT_LOG_PATH,
        wittypi_dir: Path = DEFAULT_WITTYPI_DIR,
    ) -> None:
        self._recharge_path = recharge_path
        self._boot_log_path = boot_log_path
        self._wittypi_dir = wittypi_dir
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
        return self._read_voltage(REG_BATTERY_V_INT, REG_BATTERY_V_DEC, fallback=3.82)

    def usb_voltage(self) -> float:
        return self._read_voltage(REG_USB_V_INT, REG_USB_V_DEC, fallback=0.0)

    def battery_percentage(self) -> int:
        return _voltage_to_percent(self.battery_voltage())

    def is_charging(self) -> bool:
        """True while external (USB-C) power is connected to WittyPi's own input.

        No fallback on failure: the Vout rail reads ~5.2V from either power source, so
        any heuristic built on it returns a confident wrong answer. False is the safe
        default — it selects the normal schedule, whose hard shutdown is the backstop
        that keeps battery-only operation from draining the cell.
        """
        if self._bus is None:
            return False
        try:
            return self._bus.read_byte_data(I2C_ADDRESS, REG_POWER_MODE) == POWER_MODE_EXTERNAL
        except Exception as e:
            logger.debug("I2C read error (power mode): %s — assuming battery", e)
            return False

    def _apply_schedule(self, schedule_name: str) -> bool:
        """Copy <wittypi_dir>/schedules/<schedule_name> to <wittypi_dir>/schedule.wpi
        and re-source runScript.sh to recompute/arm the RTC alarms — the same two
        steps wittyPi.sh's "Choose schedule script" menu option performs internally.
        Never raises; logs and returns False on failure so a broken/missing WittyPi
        install doesn't crash the app (updating the display is the primary job)."""
        src = self._wittypi_dir / "schedules" / schedule_name
        dest = self._wittypi_dir / "schedule.wpi"
        try:
            subprocess.run(
                ["sudo", "cp", str(src), str(dest)],
                check=True, capture_output=True, timeout=10,
            )
            subprocess.run(
                ["sudo", "bash", "-c",
                 f"cd {shlex.quote(str(self._wittypi_dir))} && . ./runScript.sh"],
                check=True, capture_output=True, timeout=30,
            )
            logger.info("Applied WittyPi schedule: %s", schedule_name)
            return True
        except Exception as e:
            logger.warning("Failed to apply WittyPi schedule %s: %s", schedule_name, e)
            return False

    def reconcile_schedule(self) -> bool:
        """Idempotently ensure <wittypi_dir>/schedule.wpi matches the schedule
        appropriate for the current charging state: charging -> the WAIT variant
        that suppresses WittyPi's own hard shutdown, letting the app stay awake;
        not charging -> the hard grid, WittyPi's shutdown backstop for battery-only
        operation. Safe and cheap to call on every boot in every code path
        (debug/charging/normal) — self-heals a schedule left in the wrong state by
        a crash mid-session. Skips the actual apply when the correct file is
        already active, to avoid needless RTC-alarm recomputation on every routine
        boot. Never raises."""
        charging = self.is_charging()
        target_name = SCHEDULE_CHARGING_NAME if charging else SCHEDULE_NORMAL_NAME
        target_src = self._wittypi_dir / "schedules" / target_name
        dest = self._wittypi_dir / "schedule.wpi"
        logger.info("Reconciling WittyPi schedule: charging=%s -> target=%s", charging, target_name)
        try:
            result = subprocess.run(
                ["sudo", "diff", "-q", str(target_src), str(dest)],
                capture_output=True, timeout=10,
            )
            if result.returncode == 0:
                logger.info("Schedule already matches %s — skipping apply", target_name)
                return True
        except Exception as e:
            logger.info("Could not compare schedule files (%s) — will attempt apply", e)
        return self._apply_schedule(target_name)

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

    def log_boot(self) -> None:
        """Append one CSV row with current battery state."""
        try:
            write_header = not self._boot_log_path.exists()
            with open(self._boot_log_path, "a") as f:
                if write_header:
                    f.write("timestamp,battery_v,battery_pct,usb_v,charging\n")
                ts = datetime.now().isoformat(timespec="seconds")
                bv = f"{self.battery_voltage():.2f}"
                bp = str(self.battery_percentage())
                uv = f"{self.usb_voltage():.2f}"
                ch = "true" if self.is_charging() else "false"
                f.write(f"{ts},{bv},{bp},{uv},{ch}\n")
        except OSError as e:
            logger.warning("Could not write boot log: %s", e)
