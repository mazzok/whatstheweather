import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_smbus():
    """Patch smbus2 so tests run without I2C hardware."""
    mock_bus = MagicMock()
    with patch("src.wittypi.SMBus", return_value=mock_bus):
        yield mock_bus


@pytest.fixture
def wittypi(mock_smbus):
    from src.wittypi import WittyPi
    return WittyPi()


class TestVoltageReading:
    def test_battery_voltage(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 3,
            0x02: 92,
        }.get(reg, 0)
        assert wittypi.battery_voltage() == pytest.approx(3.92, abs=0.01)

    def test_usb_voltage(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x03: 5,
            0x04: 12,
        }.get(reg, 0)
        assert wittypi.usb_voltage() == pytest.approx(5.12, abs=0.01)

    def test_battery_voltage_fallback_on_error(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = OSError("I2C error")
        assert wittypi.battery_voltage() == 3.7

    def test_usb_voltage_fallback_on_error(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = OSError("I2C error")
        assert wittypi.usb_voltage() == 0.0
