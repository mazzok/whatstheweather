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


class TestOffGridDays:
    def test_first_run_no_file(self, mock_ina, tmp_path):
        """First run with no persistence file creates it and returns 0."""
        mock_ina.current.return_value = -100.0  # not charging
        mock_ina.voltage.return_value = 3.9
        monitor = BatteryMonitor(recharge_path=tmp_path / ".weather_recharge")
        days = monitor.get_off_grid_days()
        assert days == 0
        # File should now exist
        data = json.loads((tmp_path / ".weather_recharge").read_text())
        assert data["date"] == str(date.today())
        assert data["percentage"] == 74  # 3.9V => 74% (int truncation)

    def test_returns_days_since_last_recharge(self, mock_ina, tmp_path):
        """Returns correct day count from saved date."""
        from datetime import timedelta

        mock_ina.current.return_value = -100.0
        mock_ina.voltage.return_value = 3.6  # 50%
        recharge_path = tmp_path / ".weather_recharge"
        five_days_ago = str(date.today() - timedelta(days=5))
        recharge_path.write_text(json.dumps({"date": five_days_ago, "percentage": 80}))
        monitor = BatteryMonitor(recharge_path=recharge_path)
        days = monitor.get_off_grid_days()
        assert days == 5

    def test_resets_on_charge_increase(self, mock_ina, tmp_path):
        """Resets counter when charging and percentage increased."""
        mock_ina.current.return_value = 200.0  # charging
        mock_ina.voltage.return_value = 3.9  # 75%
        recharge_path = tmp_path / ".weather_recharge"
        recharge_path.write_text(json.dumps({"date": "2026-04-01", "percentage": 50}))
        monitor = BatteryMonitor(recharge_path=recharge_path)
        days = monitor.get_off_grid_days()
        assert days == 0
        data = json.loads(recharge_path.read_text())
        assert data["date"] == str(date.today())
        assert data["percentage"] == 74  # 3.9V => 74% (int truncation)

    def test_no_reset_when_charging_but_no_increase(self, mock_ina, tmp_path):
        """No reset if charging but percentage hasn't increased."""
        mock_ina.current.return_value = 200.0  # charging
        mock_ina.voltage.return_value = 3.6  # 50%
        recharge_path = tmp_path / ".weather_recharge"
        recharge_path.write_text(json.dumps({"date": "2026-04-10", "percentage": 50}))
        monitor = BatteryMonitor(recharge_path=recharge_path)
        days = monitor.get_off_grid_days()
        assert days == (date.today() - date(2026, 4, 10)).days

    def test_no_reset_when_not_charging(self, mock_ina, tmp_path):
        """No reset if percentage increased but not charging (measurement noise)."""
        mock_ina.current.return_value = -100.0  # not charging
        mock_ina.voltage.return_value = 3.9  # 75%
        recharge_path = tmp_path / ".weather_recharge"
        recharge_path.write_text(json.dumps({"date": "2026-04-10", "percentage": 50}))
        monitor = BatteryMonitor(recharge_path=recharge_path)
        days = monitor.get_off_grid_days()
        assert days == (date.today() - date(2026, 4, 10)).days

    def test_updates_percentage_on_normal_operation(self, mock_ina, tmp_path):
        """Normal operation saves current percentage but keeps date."""
        mock_ina.current.return_value = -100.0
        mock_ina.voltage.return_value = 3.6  # 50%
        recharge_path = tmp_path / ".weather_recharge"
        recharge_path.write_text(json.dumps({"date": "2026-04-10", "percentage": 80}))
        monitor = BatteryMonitor(recharge_path=recharge_path)
        monitor.get_off_grid_days()
        data = json.loads(recharge_path.read_text())
        assert data["date"] == "2026-04-10"  # date unchanged
        assert data["percentage"] == 50  # updated to current
