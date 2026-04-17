import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.battery import BatteryMonitor

RECHARGE_FILE_CONTENT = json.dumps({"date": "2026-04-10", "percentage": 50})


@pytest.fixture
def mock_ina():
    """Patch INA219 so tests run without I2C hardware."""
    with patch("src.battery.INA219") as cls:
        instance = MagicMock()
        cls.return_value = instance
        instance.voltage.return_value = 3.9
        instance.current.return_value = -120.0  # discharging
        yield instance


@pytest.fixture
def monitor(mock_ina, tmp_path):
    return BatteryMonitor(recharge_path=tmp_path / ".weather_recharge")


def test_voltage(monitor, mock_ina):
    mock_ina.voltage.return_value = 3.85
    assert monitor.voltage() == 3.85


def test_current(monitor, mock_ina):
    mock_ina.current.return_value = -200.0
    assert monitor.current() == -200.0


def test_percentage_full(monitor, mock_ina):
    mock_ina.voltage.return_value = 4.2
    assert monitor.percentage() == 100


def test_percentage_empty(monitor, mock_ina):
    mock_ina.voltage.return_value = 3.0
    assert monitor.percentage() == 0


def test_percentage_mid(monitor, mock_ina):
    mock_ina.voltage.return_value = 3.6
    assert monitor.percentage() == 50


def test_percentage_clamps_above(monitor, mock_ina):
    mock_ina.voltage.return_value = 4.5
    assert monitor.percentage() == 100


def test_percentage_clamps_below(monitor, mock_ina):
    mock_ina.voltage.return_value = 2.5
    assert monitor.percentage() == 0


def test_is_charging_true(monitor, mock_ina):
    mock_ina.current.return_value = 150.0
    assert monitor.is_charging() is True


def test_is_charging_false(monitor, mock_ina):
    mock_ina.current.return_value = -120.0
    assert monitor.is_charging() is False


def test_is_charging_zero_is_false(monitor, mock_ina):
    mock_ina.current.return_value = 0.0
    assert monitor.is_charging() is False
