import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

from src.config import load_config
from src.location import get_location
from src.weather import get_weather
from src.renderer import render_display
from src.display import update_display_4gray
from src.wittypi import WittyPi

CONFIG_PATH = "config.yaml"

NETWORK_TIMEOUT = 30
NETWORK_CHECK_INTERVAL = 2


def _wait_for_network(timeout: int = NETWORK_TIMEOUT) -> bool:
    """Wait up to timeout seconds for network connectivity. Returns True if connected."""
    logger = logging.getLogger(__name__)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            subprocess.run(
                ["ping", "-c", "1", "-W", "1", "1.1.1.1"],
                capture_output=True,
                timeout=3,
            )
            return True
        except Exception:
            pass
        time.sleep(NETWORK_CHECK_INTERVAL)
    logger.warning("Network not available after %ds", timeout)
    return False


def run_once(config: dict, battery_pct: int, off_grid_days: int) -> None:
    logger = logging.getLogger(__name__)

    has_network = _wait_for_network()

    if not has_network:
        # No network: render with error, battery info still shown
        image = render_display(
            get_weather(0, 0),  # will fail and return error WeatherData
            battery_pct=battery_pct,
            off_grid_days=off_grid_days,
            error="Kein Netz",
        )
        update_display_4gray(image)
        return

    # 1. Get location
    location = get_location()
    if location is None:
        logger.error("Could not determine location")
        lat, lon, city = 48.2082, 16.3738, config.get("city", "Wien")
    else:
        lat, lon, city = location
        city = config.get("city", city)

    # 2. Get weather data
    weather = get_weather(lat, lon)

    # 3. Render
    image = render_display(weather, battery_pct=battery_pct, off_grid_days=off_grid_days, city=city)

    # 4. Update display
    if config["debug"]:
        preview_path = "preview.png"
        image.save(preview_path)
        logger.info("Preview saved to %s", preview_path)
        answer = input("Display aktualisieren? [j/N] ").strip().lower()
        if answer == "j":
            update_display_4gray(image)
            logger.info("Display updated")
        else:
            logger.info("Display update skipped")
    else:
        update_display_4gray(image)


def main() -> None:
    parser = argparse.ArgumentParser(description="Weather display")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode (overrides config)")
    args = parser.parse_args()

    config = load_config(CONFIG_PATH)
    if args.debug:
        config["debug"] = True

    level = logging.DEBUG if config["debug"] else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)] if config["debug"]
        else [logging.FileHandler(Path.home() / ".weather_display.log")],
    )

    logger = logging.getLogger(__name__)
    logger.info("Weather display starting (debug=%s)", config["debug"])

    wittypi = WittyPi()

    if config["debug"]:
        while True:
            battery_pct = wittypi.battery_percentage()
            off_grid_days = wittypi.get_off_grid_days()
            run_once(config, battery_pct, off_grid_days)
            logger.info("Next update in %d seconds", config["interval"])
            time.sleep(config["interval"])
    else:
        battery_pct = wittypi.battery_percentage()
        off_grid_days = wittypi.get_off_grid_days()
        run_once(config, battery_pct, off_grid_days)
        logger.info("Shutting down...")
        subprocess.run(["sudo", "shutdown", "-h", "now"])


if __name__ == "__main__":
    main()
