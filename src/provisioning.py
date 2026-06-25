# src/provisioning.py
from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def run_provisioning(ssid: str, password: str, timeout: int = 900) -> bool:
    """Start Balena WiFi Connect and wait for successful network configuration.

    Returns True if the user configured WiFi within `timeout` seconds.
    Returns False on timeout or if the wifi-connect binary is not found.
    """
    try:
        proc = subprocess.Popen(
            ["sudo", "wifi-connect", "--ssid", ssid, "--password", password]
        )
    except FileNotFoundError:
        logger.error("wifi-connect binary not found at /usr/local/sbin/wifi-connect")
        return False

    try:
        proc.wait(timeout=timeout)
        logger.info("wifi-connect exited — network configured")
        return True
    except subprocess.TimeoutExpired:
        logger.warning("Provisioning timed out after %ds", timeout)
        proc.terminate()
        return False
