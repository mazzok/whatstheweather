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


class TestBatteryPercentage:
    def test_full(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 4, 0x02: 20,
        }.get(reg, 0)
        assert wittypi.battery_percentage() == 100

    def test_empty(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 3, 0x02: 0,
        }.get(reg, 0)
        assert wittypi.battery_percentage() == 0

    def test_mid(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 3, 0x02: 60,
        }.get(reg, 0)
        assert wittypi.battery_percentage() == 50

    def test_clamps_above(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 4, 0x02: 50,
        }.get(reg, 0)
        assert wittypi.battery_percentage() == 100

    def test_clamps_below(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 2, 0x02: 50,
        }.get(reg, 0)
        assert wittypi.battery_percentage() == 0

    def test_fallback(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = OSError("I2C error")
        assert wittypi.battery_percentage() == 50


class TestIsCharging:
    def test_usb_connected(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x03: 5, 0x04: 10,
        }.get(reg, 0)
        assert wittypi.is_charging() is True

    def test_usb_disconnected(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x03: 0, 0x04: 0,
        }.get(reg, 0)
        assert wittypi.is_charging() is False

    def test_usb_at_threshold(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x03: 4, 0x04: 0,
        }.get(reg, 0)
        assert wittypi.is_charging() is False

    def test_fallback_not_charging(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = OSError("I2C error")
        assert wittypi.is_charging() is False


class TestOffGridDays:
    def test_first_run_no_file(self, mock_smbus, tmp_path):
        from src.wittypi import WittyPi
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 3, 0x02: 90,
            0x03: 0, 0x04: 0,
        }.get(reg, 0)
        wp = WittyPi(recharge_path=tmp_path / ".weather_recharge")
        days = wp.get_off_grid_days()
        assert days == 0
        data = json.loads((tmp_path / ".weather_recharge").read_text())
        assert data["date"] == str(date.today())
        assert data["percentage"] == 75

    def test_returns_days_since_last_recharge(self, mock_smbus, tmp_path):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 3, 0x02: 60,
            0x03: 0, 0x04: 0,
        }.get(reg, 0)
        recharge_path = tmp_path / ".weather_recharge"
        five_days_ago = str(date.today() - timedelta(days=5))
        recharge_path.write_text(json.dumps({"date": five_days_ago, "percentage": 80}))
        from src.wittypi import WittyPi
        wp = WittyPi(recharge_path=recharge_path)
        assert wp.get_off_grid_days() == 5

    def test_resets_on_charging(self, mock_smbus, tmp_path):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 3, 0x02: 90,
            0x03: 5, 0x04: 10,
        }.get(reg, 0)
        recharge_path = tmp_path / ".weather_recharge"
        recharge_path.write_text(json.dumps({"date": "2026-04-01", "percentage": 50}))
        from src.wittypi import WittyPi
        wp = WittyPi(recharge_path=recharge_path)
        assert wp.get_off_grid_days() == 0
        data = json.loads(recharge_path.read_text())
        assert data["date"] == str(date.today())

    def test_no_reset_when_not_charging(self, mock_smbus, tmp_path):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 3, 0x02: 90,
            0x03: 0, 0x04: 0,
        }.get(reg, 0)
        recharge_path = tmp_path / ".weather_recharge"
        recharge_path.write_text(json.dumps({"date": "2026-04-10", "percentage": 50}))
        from src.wittypi import WittyPi
        wp = WittyPi(recharge_path=recharge_path)
        days = wp.get_off_grid_days()
        assert days == (date.today() - date(2026, 4, 10)).days


class TestLogBoot:
    def test_creates_csv_with_header_and_row(self, mock_smbus, tmp_path):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 3, 0x02: 92,
            0x03: 0, 0x04: 0,
        }.get(reg, 0)
        from src.wittypi import WittyPi
        log_path = tmp_path / "battery_log.csv"
        wp = WittyPi(
            recharge_path=tmp_path / ".weather_recharge",
            boot_log_path=log_path,
        )
        wp.log_boot()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert lines[0] == "timestamp,battery_v,battery_pct,usb_v,charging"
        row = lines[1].split(",")
        assert row[1] == "3.92"
        assert row[2] == "77"
        assert row[3] == "0.00"
        assert row[4] == "false"

    def test_appends_without_duplicate_header(self, mock_smbus, tmp_path):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 3, 0x02: 92,
            0x03: 0, 0x04: 0,
        }.get(reg, 0)
        from src.wittypi import WittyPi
        log_path = tmp_path / "battery_log.csv"
        wp = WittyPi(
            recharge_path=tmp_path / ".weather_recharge",
            boot_log_path=log_path,
        )
        wp.log_boot()
        wp.log_boot()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "timestamp,battery_v,battery_pct,usb_v,charging"

    def test_log_boot_survives_write_error(self, mock_smbus, tmp_path):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 3, 0x02: 92,
            0x03: 0, 0x04: 0,
        }.get(reg, 0)
        from src.wittypi import WittyPi
        # Point to a non-existent directory so open() fails
        log_path = tmp_path / "no_such_dir" / "battery_log.csv"
        wp = WittyPi(
            recharge_path=tmp_path / ".weather_recharge",
            boot_log_path=log_path,
        )
        # Should not raise
        wp.log_boot()
