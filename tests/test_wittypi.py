import json
import subprocess
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_smbus():
    """Patch smbus2 and subprocess so tests run without hardware.

    subprocess.run raises FileNotFoundError by default, so any test that reaches a
    shell-out path without opting in fails loudly rather than touching the host.
    Schedule tests override it locally.
    """
    mock_bus = MagicMock()
    with patch("src.wittypi.SMBus", return_value=mock_bus), \
         patch("src.wittypi.subprocess.run", side_effect=FileNotFoundError("gpio not installed")):
        yield mock_bus


@pytest.fixture
def wittypi(mock_smbus):
    from src.wittypi import WittyPi
    return WittyPi()


from src.wittypi import _voltage_to_percent


class TestVoltageToPercent:
    @pytest.mark.parametrize("voltage,expected", [
        (4.20, 100),
        (4.06, 90),
        (3.98, 80),
        (3.92, 70),
        (3.87, 60),
        (3.82, 50),
        (3.79, 40),
        (3.77, 30),
        (3.74, 20),
        (3.68, 10),
        (3.45, 0),
    ])
    def test_exact_control_points(self, voltage, expected):
        assert _voltage_to_percent(voltage) == expected

    def test_interpolates_between_control_points(self):
        # Midpoint between (3.87, 60) and (3.92, 70)
        assert _voltage_to_percent(3.895) == 65

    def test_above_full_clamps_to_100(self):
        assert _voltage_to_percent(4.50) == 100

    def test_below_empty_clamps_to_0(self):
        assert _voltage_to_percent(3.00) == 0


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
    def test_power_mode_zero_means_external_power(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x07: 0x00,
        }.get(reg, 0xFF)
        assert wittypi.is_charging() is True

    def test_power_mode_nonzero_means_battery(self, wittypi, mock_smbus):
        # 0x02 is the value observed on hardware with USB-C disconnected.
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x07: 0x02,
        }.get(reg, 0x00)
        assert wittypi.is_charging() is False

    def test_any_nonzero_power_mode_means_battery(self, wittypi, mock_smbus):
        # Only 0 means external power; don't assume 0x02 is the sole battery code.
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x07: 0x01,
        }.get(reg, 0x00)
        assert wittypi.is_charging() is False

    def test_not_charging_on_i2c_error(self, wittypi, mock_smbus):
        mock_smbus.read_byte_data.side_effect = OSError("I2C error")
        assert wittypi.is_charging() is False

    def test_not_charging_without_i2c_bus(self, tmp_path):
        from src.wittypi import WittyPi
        with patch("src.wittypi.SMBus", None):
            wp = WittyPi(recharge_path=tmp_path / ".weather_recharge")
        assert wp.is_charging() is False


class TestOffGridDays:
    def test_first_run_no_file(self, mock_smbus, tmp_path):
        from src.wittypi import WittyPi
        mock_smbus.read_byte_data.side_effect = lambda addr, reg: {
            0x01: 3, 0x02: 90,
            0x03: 0, 0x04: 0,
            0x07: 0x02,  # battery mode
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
            0x07: 0x02,  # battery mode
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
            0x07: 0x00,  # external power
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
            0x07: 0x02,  # battery mode
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
            0x07: 0x02,  # battery mode
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
            0x07: 0x02,  # battery mode
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
            0x07: 0x02,  # battery mode
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


def _cmd_matcher(diff_result=0, cp_ok=True, runscript_ok=True):
    """Build a subprocess.run side_effect that dispatches on which WittyPi
    schedule command is being invoked, based on the argv list's contents."""
    def side_effect(cmd, **kwargs):
        if "diff" in cmd:
            return MagicMock(returncode=diff_result)
        if "cp" in cmd:
            if not cp_ok:
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(returncode=0)
        if any("runScript.sh" in part for part in cmd):
            if not runscript_ok:
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(returncode=0)
        raise AssertionError(f"unexpected subprocess command: {cmd}")
    return side_effect


class TestScheduleReconciliation:
    def test_apply_schedule_success(self, wittypi):
        with patch("src.wittypi.subprocess.run", side_effect=_cmd_matcher()) as mock_run:
            assert wittypi._apply_schedule("weatherpi.wpi") is True
        cp_call = next(c for c in mock_run.call_args_list if "cp" in c.args[0])
        assert str(wittypi._wittypi_dir / "schedules" / "weatherpi.wpi") in cp_call.args[0]
        assert str(wittypi._wittypi_dir / "schedule.wpi") in cp_call.args[0]
        run_call = next(c for c in mock_run.call_args_list if "bash" in c.args[0])
        assert "runScript.sh" in run_call.args[0][-1]

    def test_apply_schedule_cp_failure_returns_false(self, wittypi):
        with patch("src.wittypi.subprocess.run", side_effect=_cmd_matcher(cp_ok=False)):
            assert wittypi._apply_schedule("weatherpi.wpi") is False

    def test_apply_schedule_runscript_failure_returns_false(self, wittypi):
        with patch("src.wittypi.subprocess.run", side_effect=_cmd_matcher(runscript_ok=False)):
            assert wittypi._apply_schedule("weatherpi.wpi") is False

    def test_reconcile_schedule_applies_charging_schedule_when_charging(self, wittypi):
        with patch("src.wittypi.subprocess.run", side_effect=_cmd_matcher(diff_result=1)) as mock_run:
            with patch.object(wittypi, "is_charging", return_value=True):
                assert wittypi.reconcile_schedule() is True
        cp_call = next(c for c in mock_run.call_args_list if "cp" in c.args[0])
        assert "weatherpi-charging.wpi" in cp_call.args[0][2]

    def test_reconcile_schedule_applies_normal_schedule_when_not_charging(self, wittypi):
        with patch("src.wittypi.subprocess.run", side_effect=_cmd_matcher(diff_result=1)) as mock_run:
            with patch.object(wittypi, "is_charging", return_value=False):
                assert wittypi.reconcile_schedule() is True
        cp_call = next(c for c in mock_run.call_args_list if "cp" in c.args[0])
        assert cp_call.args[0][2].endswith("weatherpi.wpi")
        assert "charging" not in cp_call.args[0][2]

    def test_reconcile_schedule_skips_apply_when_already_matching(self, wittypi):
        with patch("src.wittypi.subprocess.run", side_effect=_cmd_matcher(diff_result=0)) as mock_run:
            with patch.object(wittypi, "is_charging", return_value=True):
                assert wittypi.reconcile_schedule() is True
        assert len(mock_run.call_args_list) == 1
        assert "diff" in mock_run.call_args_list[0].args[0]

    def test_reconcile_schedule_attempts_apply_when_diff_errors(self, wittypi):
        with patch("src.wittypi.subprocess.run", side_effect=_cmd_matcher(diff_result=2)) as mock_run:
            with patch.object(wittypi, "is_charging", return_value=False):
                assert wittypi.reconcile_schedule() is True
        assert any("cp" in c.args[0] for c in mock_run.call_args_list)

    def test_reconcile_schedule_never_raises_on_unexpected_error(self, wittypi):
        def raise_timeout(cmd, **kwargs):
            raise TimeoutError("boom")

        with patch("src.wittypi.subprocess.run", side_effect=raise_timeout):
            with patch.object(wittypi, "is_charging", return_value=False):
                result = wittypi.reconcile_schedule()
        assert result is False
