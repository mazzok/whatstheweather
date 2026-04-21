# tests/test_config.py
import os
import tempfile
import pytest
from src.config import load_config


def test_load_config_defaults():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("debug: true\ninterval: 3600\n")
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)
    assert config["debug"] is True
    assert config["interval"] == 3600


def test_load_config_missing_file_uses_defaults():
    config = load_config("/nonexistent/path.yaml")
    assert config["debug"] is True
    assert config["interval"] == 7200


def test_load_config_production_mode():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("debug: false\ninterval: 7200\n")
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)
    assert config["debug"] is False
