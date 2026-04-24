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
from src.battery import BatteryMonitor
from src.display import update_display_4gray

CONFIG_PATH = "config.yaml"

CHARGE_POLL_INTERVAL = 300  # 5 minutes


def run_once(config: dict, battery: BatteryMonitor) -> None:
    logger = logging.getLogger(__name__)

    # 1. Get location
    location = get_location()
    if location is None:
        logger.error("Could not determine location")
        lat, lon, city = 48.2082, 16.3738, config.get("city", "Wien")
    else:
        lat, lon, city = location
        # Config override for city name
        city = config.get("city", city)

    # 2. Get weather data
    weather = get_weather(lat, lon)

    # 3. Get battery and off-grid days
    battery_pct = battery.percentage()
    off_grid_days = battery.get_off_grid_days()

    # 4. Render
    image = render_display(weather, battery_pct=battery_pct, off_grid_days=off_grid_days, city=city)

    # 5. Update display
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


def _charge_loop(config: dict, battery: BatteryMonitor) -> None:
    """Poll while charging. Exits when power is disconnected."""
    logger = logging.getLogger(__name__)
    logger.info("Charging detected — entering charge poll loop")

    while battery.is_charging():
        run_once(config, battery)
        logger.info("Charge poll: next check in %d seconds", CHARGE_POLL_INTERVAL)
        time.sleep(CHARGE_POLL_INTERVAL)

    logger.info("Charging stopped — resuming normal operation")


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

    battery = BatteryMonitor()

    if config["debug"]:
        while True:
            run_once(config, battery)
            logger.info("Next update in %d seconds", config["interval"])
            time.sleep(config["interval"])
    else:
        run_once(config, battery)

        if battery.is_charging():
            logger.info("Power connected — staying alive for timer")
        else:
            logger.info("On battery — entering deep sleep...")
            subprocess.run(["sudo", "shutdown", "-h", "now"])


if __name__ == "__main__":
    main()
