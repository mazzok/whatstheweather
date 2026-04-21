# src/location.py
import logging
import requests

GEOLOCATION_URL = "http://ip-api.com/json/?fields=status,lat,lon,city"
TIMEOUT = 10

logger = logging.getLogger(__name__)


def get_location() -> tuple[float, float] | None:
    try:
        resp = requests.get(GEOLOCATION_URL, timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.error("Geolocation request failed: HTTP %d", resp.status_code)
            return None
        data = resp.json()
        if data.get("status") != "success":
            logger.error("Geolocation failed: %s", data)
            return None
        lat = data["lat"]
        lon = data["lon"]
        logger.info("Location: %s (%.4f, %.4f)", data.get("city", "?"), lat, lon)
        return lat, lon
    except Exception as e:
        logger.error("Geolocation error: %s", e)
        return None
