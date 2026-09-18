import sys
from unittest.mock import MagicMock, patch

import pytest


class TestMainReconciliation:
    @patch("src.main.subprocess.run")
    @patch("src.main.run_once")
    @patch("src.main.WittyPi")
    @patch("src.main.load_config")
    def test_main_calls_reconcile_schedule_before_normal_branch(
        self, mock_load_config, mock_wittypi_cls, mock_run_once, mock_subprocess_run
    ):
        from src.main import main

        mock_load_config.return_value = {"debug": False, "interval": 60}
        wittypi = MagicMock()
        wittypi.is_charging.return_value = False
        wittypi.battery_percentage.return_value = 80
        wittypi.get_off_grid_days.return_value = 0
        mock_wittypi_cls.return_value = wittypi

        with patch.object(sys, "argv", ["main.py"]):
            main()

        assert wittypi.reconcile_schedule.call_count == 1
        names = [c[0] for c in wittypi.method_calls]
        assert names.index("reconcile_schedule") < names.index("is_charging")

    @patch("src.main.subprocess.run")
    @patch("src.main._run_charging_mode")
    @patch("src.main.WittyPi")
    @patch("src.main.load_config")
    def test_main_calls_reconcile_schedule_before_charging_branch(
        self, mock_load_config, mock_wittypi_cls, mock_run_charging_mode, mock_subprocess_run
    ):
        from src.main import main

        mock_load_config.return_value = {"debug": False, "interval": 60}
        wittypi = MagicMock()
        wittypi.is_charging.return_value = True
        mock_wittypi_cls.return_value = wittypi

        with patch.object(sys, "argv", ["main.py"]):
            main()

        assert wittypi.reconcile_schedule.call_count == 1
        mock_run_charging_mode.assert_called_once()
        names = [c[0] for c in wittypi.method_calls]
        assert names.index("reconcile_schedule") < names.index("is_charging")

    @patch("src.main.run_once")
    @patch("src.main.WittyPi")
    @patch("src.main.load_config")
    @patch("src.main.time.sleep")
    def test_main_calls_reconcile_schedule_in_debug_mode(
        self, mock_sleep, mock_load_config, mock_wittypi_cls, mock_run_once
    ):
        from src.main import main

        mock_load_config.return_value = {"debug": True, "interval": 60}
        wittypi = MagicMock()
        mock_wittypi_cls.return_value = wittypi

        class StopLoop(Exception):
            pass

        mock_sleep.side_effect = StopLoop()

        with patch.object(sys, "argv", ["main.py", "--debug"]):
            with pytest.raises(StopLoop):
                main()

        assert wittypi.reconcile_schedule.call_count == 1
