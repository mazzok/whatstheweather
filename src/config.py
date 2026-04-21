# src/config.py
import yaml
import logging

DEFAULTS = {
    "debug": True,
    "interval": 7200,
}


def load_config(path: str) -> dict:
    config = dict(DEFAULTS)
    try:
        with open(path, "r") as f:
            user_config = yaml.safe_load(f) or {}
        config.update(user_config)
    except FileNotFoundError:
        logging.warning("Config file %s not found, using defaults", path)
    return config
