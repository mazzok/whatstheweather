from unittest.mock import MagicMock, call, patch

import pytest


class TestRunChargingMode:
    @patch("src.main.run_once")
    @patch("src.main.time.sleep")
    def test_calls_run_once_immediately_on_entry(self, mock_sleep, mock_run_once):
        """run_once fires before any sleep when charger is connected."""
        from src.main import _run_charging_mode

        wittypi = MagicMock()
        # is_charging: True (outer loop enters), True (inner 60s chunk), False (outer exits)
        wittypi.is_charging.side_effect = [True, True, False]
        wittypi.battery_percentage.return_value = 75
        wittypi.get_off_grid_days.return_value = 0

        _run_charging_mode({"interval": 60}, wittypi)

        # First call is run_once (before any sleep)
        assert mock_run_once.call_args_list[0] == call({"interval": 60}, 75, 0)

    @patch("src.main.run_once")
    @patch("src.main.time.sleep")
    def test_final_run_once_after_charger_removed(self, mock_sleep, mock_run_once):
        """A final run_once fires after charger is removed, then function returns."""
        from src.main import _run_charging_mode

        wittypi = MagicMock()
        wittypi.is_charging.side_effect = [True, True, False]
        wittypi.battery_percentage.return_value = 80
        wittypi.get_off_grid_days.return_value = 2

        _run_charging_mode({"interval": 60}, wittypi)

        # 1 in loop + 1 final
        assert mock_run_once.call_count == 2
        # Last call is the final update
        assert mock_run_once.call_args_list[-1] == call({"interval": 60}, 80, 2)

    @patch("src.main.run_once")
    @patch("src.main.time.sleep")
    def test_sleeps_in_60s_chunks_for_longer_interval(self, mock_sleep, mock_run_once):
        """A 180s interval produces exactly 3 × sleep(60) calls."""
        from src.main import _run_charging_mode

        wittypi = MagicMock()
        # outer: True; inner: True, True, True (3 chunks × 60s, remaining hits 0); outer: False
        wittypi.is_charging.side_effect = [True, True, True, True, False]
        wittypi.battery_percentage.return_value = 60
        wittypi.get_off_grid_days.return_value = 1

        _run_charging_mode({"interval": 180}, wittypi)

        assert mock_sleep.call_count == 3
        mock_sleep.assert_called_with(60)

    @patch("src.main.run_once")
    @patch("src.main.time.sleep")
    def test_exits_inner_sleep_immediately_on_charger_removal(self, mock_sleep, mock_run_once):
        """If charger is removed mid-sleep, the inner loop exits on next 60s boundary."""
        from src.main import _run_charging_mode

        wittypi = MagicMock()
        # outer: True; inner: True (1st chunk), False (exits early — charger gone); outer: False
        wittypi.is_charging.side_effect = [True, True, False, False]
        wittypi.battery_percentage.return_value = 70
        wittypi.get_off_grid_days.return_value = 0

        _run_charging_mode({"interval": 180}, wittypi)

        # Only 1 sleep chunk before charger removed
        assert mock_sleep.call_count == 1

    @patch("src.main.run_once")
    @patch("src.main.time.sleep")
    def test_multiple_full_cycles(self, mock_sleep, mock_run_once):
        """Two complete charge cycles before charger is removed."""
        from src.main import _run_charging_mode

        wittypi = MagicMock()
        # cycle 1: outer True, inner True (1 chunk×60s), outer True again
        # cycle 2: outer True, inner True (1 chunk×60s), outer False
        wittypi.is_charging.side_effect = [True, True, True, True, False]
        wittypi.battery_percentage.return_value = 90
        wittypi.get_off_grid_days.return_value = 0

        _run_charging_mode({"interval": 60}, wittypi)

        # 2 in-loop + 1 final
        assert mock_run_once.call_count == 3
        assert mock_sleep.call_count == 2
