"""rtc.py — DS3231 RTC alarm for scheduled wake from halt."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

I2C_ADDRESS = 0x68

# DS3231 registers
REG_SECONDS = 0x00
REG_ALARM1_SECONDS = 0x07
REG_CONTROL = 0x0E
REG_STATUS = 0x0F


def _bcd_to_int(bcd: int) -> int:
    return (bcd >> 4) * 10 + (bcd & 0x0F)


def _int_to_bcd(val: int) -> int:
    return ((val // 10) << 4) | (val % 10)


class DS3231:
    def __init__(self) -> None:
        try:
            from smbus2 import SMBus
            self._bus = SMBus(1)
        except Exception as e:
            logger.warning("DS3231 not available: %s", e)
            self._bus = None

    def _read(self, reg: int) -> int:
        return self._bus.read_byte_data(I2C_ADDRESS, reg)

    def _write(self, reg: int, val: int) -> None:
        self._bus.write_byte_data(I2C_ADDRESS, reg, val)

    def now(self) -> datetime:
        """Read current time from DS3231."""
        s = _bcd_to_int(self._read(REG_SECONDS) & 0x7F)
        m = _bcd_to_int(self._read(0x01))
        h = _bcd_to_int(self._read(0x02) & 0x3F)
        d = _bcd_to_int(self._read(0x04))
        mo = _bcd_to_int(self._read(0x05) & 0x1F)
        y = _bcd_to_int(self._read(0x06)) + 2000
        return datetime(y, mo, d, h, m, s)

    def set_alarm(self, seconds: int) -> bool:
        """Set Alarm 1 to fire after `seconds` from now.

        Configures the DS3231 to pull SQW/INT low when the alarm
        matches hours, minutes, and seconds (A1M4=1, A1M3=0, A1M2=0, A1M1=0).
        Returns True on success.
        """
        if self._bus is None:
            logger.warning("DS3231 not available — cannot set alarm")
            return False

        target = self.now() + timedelta(seconds=seconds)
        logger.info("Setting DS3231 alarm for %s (in %d seconds)", target, seconds)

        # Write Alarm 1 registers: seconds, minutes, hours, day
        self._write(REG_ALARM1_SECONDS, _int_to_bcd(target.second))       # A1M1=0
        self._write(REG_ALARM1_SECONDS + 1, _int_to_bcd(target.minute))   # A1M2=0
        self._write(REG_ALARM1_SECONDS + 2, _int_to_bcd(target.hour))     # A1M3=0
        self._write(REG_ALARM1_SECONDS + 3, 0x80 | _int_to_bcd(target.day))  # A1M4=1 (match h/m/s only)

        # Clear alarm 1 flag (A1F) in status register
        status = self._read(REG_STATUS)
        self._write(REG_STATUS, status & ~0x01)

        # Enable alarm 1 interrupt: set A1IE=1, INTCN=1
        control = self._read(REG_CONTROL)
        control |= 0x05   # bit 0 = A1IE, bit 2 = INTCN
        control &= ~0x02  # bit 1 = A2IE off
        self._write(REG_CONTROL, control)

        logger.info("DS3231 alarm set — SQW/INT will go LOW at %s", target)
        return True

    def clear_alarm(self) -> None:
        """Clear alarm 1 flag so SQW/INT goes high again."""
        if self._bus is None:
            return
        status = self._read(REG_STATUS)
        self._write(REG_STATUS, status & ~0x01)
