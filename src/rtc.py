"""rtc.py — DS3231 RTC alarm for scheduled wake from halt.

Uses the kernel RTC interface (/dev/rtc0) instead of raw I2C,
since the i2c-rtc overlay claims the device exclusively.
"""

from __future__ import annotations

import ctypes
import fcntl
import logging
import struct
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ioctl numbers from <linux/rtc.h>
RTC_RD_TIME = 0x80247009
RTC_ALM_SET = 0x40247007
RTC_ALM_READ = 0x80247008
RTC_AIE_ON = 0x40047001
RTC_AIE_OFF = 0x40047002

# struct rtc_time layout: 9 ints (sec, min, hour, mday, mon, year, wday, yday, isdst)
RTC_TIME_FMT = "9i"


def _pack_rtc_time(dt: datetime) -> bytes:
    return struct.pack(
        RTC_TIME_FMT,
        dt.second, dt.minute, dt.hour,
        dt.day, dt.month - 1, dt.year - 1900,
        dt.weekday(), 0, -1,
    )


def _unpack_rtc_time(buf: bytes) -> datetime:
    s, m, h, d, mo, y, _wday, _yday, _isdst = struct.unpack(RTC_TIME_FMT, buf)
    return datetime(y + 1900, mo + 1, d, h, m, s)


class DS3231:
    def __init__(self, device: str = "/dev/rtc0") -> None:
        self._device = device
        self._available = True
        try:
            with open(device, "rb") as f:
                buf = bytearray(struct.calcsize(RTC_TIME_FMT))
                fcntl.ioctl(f.fileno(), RTC_RD_TIME, buf)
            logger.debug("DS3231 available at %s", device)
        except Exception as e:
            logger.warning("DS3231 not available: %s", e)
            self._available = False

    def now(self) -> datetime | None:
        """Read current time from DS3231."""
        if not self._available:
            return None
        with open(self._device, "rb") as f:
            buf = bytearray(struct.calcsize(RTC_TIME_FMT))
            fcntl.ioctl(f.fileno(), RTC_RD_TIME, buf)
        return _unpack_rtc_time(buf)

    def set_alarm(self, seconds: int) -> bool:
        """Set RTC alarm to fire after `seconds` from now.

        Uses the kernel RTC alarm interface. When the alarm fires,
        the DS3231 SQW/INT pin goes LOW, which triggers gpio-shutdown
        to wake the Pi from halt.
        """
        if not self._available:
            logger.warning("DS3231 not available — cannot set alarm")
            return False

        target = self.now() + timedelta(seconds=seconds)
        logger.info("Setting RTC alarm for %s (in %d seconds)", target, seconds)

        alarm_buf = _pack_rtc_time(target)

        with open(self._device, "wb") as f:
            fd = f.fileno()
            # Disable any existing alarm
            fcntl.ioctl(fd, RTC_AIE_OFF, 0)
            # Set new alarm time
            fcntl.ioctl(fd, RTC_ALM_SET, alarm_buf)
            # Enable alarm interrupt
            fcntl.ioctl(fd, RTC_AIE_ON, 0)

        logger.info("RTC alarm set — SQW/INT will go LOW at %s", target)
        return True

    def clear_alarm(self) -> None:
        """Disable alarm interrupt."""
        if not self._available:
            return
        try:
            with open(self._device, "wb") as f:
                fcntl.ioctl(f.fileno(), RTC_AIE_OFF, 0)
        except Exception as e:
            logger.warning("Could not clear RTC alarm: %s", e)
