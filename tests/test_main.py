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


class TestChargingIndicatorThreading:
    @patch("src.main.subprocess.run")
    @patch("src.main.update_display_4gray")
    @patch("src.main.render_display")
    @patch("src.main.get_weather")
    @patch("src.main.get_location")
    @patch("src.main._wait_for_network", return_value=True)
    def test_run_once_passes_charging_true_to_render_display(
        self, mock_wait, mock_get_location, mock_get_weather, mock_render, mock_update, mock_subprocess_run
    ):
        from src.main import run_once

        mock_get_location.return_value = (48.2, 16.3, "Wien")
        mock_get_weather.return_value = MagicMock(error="")

        run_once({"debug": False, "city": "Wien"}, battery_pct=80, off_grid_days=0, charging=True)

        _, kwargs = mock_render.call_args
        assert kwargs["charging"] is True

    @patch("src.main.subprocess.run")
    @patch("src.main.update_display_4gray")
    @patch("src.main.render_display")
    @patch("src.main.get_weather")
    @patch("src.main.get_location")
    @patch("src.main._wait_for_network", return_value=True)
    def test_run_once_passes_charging_false_to_render_display(
        self, mock_wait, mock_get_location, mock_get_weather, mock_render, mock_update, mock_subprocess_run
    ):
        from src.main import run_once

        mock_get_location.return_value = (48.2, 16.3, "Wien")
        mock_get_weather.return_value = MagicMock(error="")

        run_once({"debug": False, "city": "Wien"}, battery_pct=80, off_grid_days=0, charging=False)

        _, kwargs = mock_render.call_args
        assert kwargs["charging"] is False

    @patch("src.main.update_display_4gray")
    @patch("src.main.render_display")
    @patch("src.main.run_provisioning", return_value=False)
    @patch("src.main.render_provisioning_screen")
    @patch("src.main._wait_for_network", return_value=False)
    def test_run_once_no_network_error_path_passes_charging(
        self, mock_wait, mock_render_prov, mock_run_prov, mock_render, mock_update
    ):
        from src.main import run_once

        run_once(
            {"debug": False, "provisioning_ssid": "x", "provisioning_password": "y"},
            battery_pct=80, off_grid_days=0, charging=True,
        )

        _, kwargs = mock_render.call_args
        assert kwargs["charging"] is True

    @patch("src.main.subprocess.run")
    @patch("src.main.run_once")
    @patch("src.main.WittyPi")
    @patch("src.main.load_config")
    def test_main_charging_branch_loop_passes_charging_true(
        self, mock_load_config, mock_wittypi_cls, mock_run_once, mock_subprocess_run
    ):
        from src.main import main

        mock_load_config.return_value = {"debug": False, "interval": 60}
        wittypi = MagicMock()
        # Call order: main()'s elif check, _run_charging_mode's outer while
        # condition (loop body runs once), the inner sleep-loop's condition
        # (False so it skips sleeping), then the outer while re-check (False,
        # exiting to the final update).
        wittypi.is_charging.side_effect = [True, True, False, False]
        wittypi.battery_percentage.return_value = 80
        wittypi.get_off_grid_days.return_value = 0
        mock_wittypi_cls.return_value = wittypi

        with patch.object(sys, "argv", ["main.py"]):
            main()

        first_call_kwargs = mock_run_once.call_args_list[0].kwargs
        assert first_call_kwargs["charging"] is True

    @patch("src.main.subprocess.run")
    @patch("src.main.run_once")
    @patch("src.main.WittyPi")
    @patch("src.main.load_config")
    def test_main_charging_branch_final_update_passes_charging_false(
        self, mock_load_config, mock_wittypi_cls, mock_run_once, mock_subprocess_run
    ):
        from src.main import main

        mock_load_config.return_value = {"debug": False, "interval": 60}
        wittypi = MagicMock()
        wittypi.is_charging.side_effect = [True, True, False, False]
        wittypi.battery_percentage.return_value = 80
        wittypi.get_off_grid_days.return_value = 0
        mock_wittypi_cls.return_value = wittypi

        with patch.object(sys, "argv", ["main.py"]):
            main()

        final_call_kwargs = mock_run_once.call_args_list[-1].kwargs
        assert final_call_kwargs["charging"] is False
