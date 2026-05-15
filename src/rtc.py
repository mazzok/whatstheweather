"""rtc.py — DS3231 RTC alarm for scheduled wake from halt."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

WAKEALARM_PATH = "/sys/class/rtc/rtc0/wakealarm"


class DS3231:
    def set_alarm(self, seconds: int) -> bool:
        """Set RTC wake alarm N seconds from now via sysfs.

        Writes +N to /sys/class/rtc/rtc0/wakealarm. When the alarm
        fires, the DS3231 SQW/INT pin goes LOW, triggering
        gpio-shutdown to wake the Pi from halt.
        """
        logger.info("Setting RTC wake alarm in %d seconds", seconds)
        try:
            # Clear any existing alarm first
            subprocess.run(
                ["sh", "-c", f"echo 0 > {WAKEALARM_PATH}"],
                check=True,
            )
            # Set new alarm
            subprocess.run(
                ["sh", "-c", f"echo +{seconds} > {WAKEALARM_PATH}"],
                check=True,
            )
            logger.info("RTC alarm set (%d seconds from now)", seconds)
            return True
        except Exception as e:
            logger.error("Failed to set RTC alarm: %s", e)
            return False
