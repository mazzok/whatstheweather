"""rtc.py — DS3231 RTC alarm for scheduled wake from halt."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


class DS3231:
    def __init__(self, device="/dev/rtc0"):
        self._device = device

    def set_alarm(self, seconds):
        """Set RTC wake alarm N seconds from now using rtcwake."""
        logger.info("Setting RTC wake alarm in %d seconds", seconds)
        try:
            result = subprocess.run(
                ["rtcwake", "-d", self._device, "-m", "no", "-s", str(seconds)],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                logger.info("RTC alarm set: %s", result.stdout.strip())
                return True
            logger.error("rtcwake failed: %s", result.stderr.strip())
            return False
        except Exception as e:
            logger.error("rtcwake error: %s", e)
            return False
