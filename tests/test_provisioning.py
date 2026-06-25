# tests/test_provisioning.py
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest


class TestRunProvisioning:
    def test_returns_true_on_success(self):
        with patch("src.provisioning.subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.wait.return_value = 0
            mock_popen.return_value = proc
            from src.provisioning import run_provisioning
            result = run_provisioning("TestSSID", "testpass", timeout=10)
        assert result is True

    def test_calls_wifi_connect_with_ssid_and_password(self):
        with patch("src.provisioning.subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.wait.return_value = 0
            mock_popen.return_value = proc
            from src.provisioning import run_provisioning
            run_provisioning("MyNet", "s3cr3t", timeout=10)
        mock_popen.assert_called_once_with(
            ["sudo", "wifi-connect", "--ssid", "MyNet", "--password", "s3cr3t"]
        )

    def test_returns_false_on_timeout(self):
        with patch("src.provisioning.subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.wait.side_effect = subprocess.TimeoutExpired(cmd="wifi-connect", timeout=10)
            mock_popen.return_value = proc
            from src.provisioning import run_provisioning
            result = run_provisioning("TestSSID", "testpass", timeout=10)
        assert result is False

    def test_terminates_subprocess_on_timeout(self):
        with patch("src.provisioning.subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.wait.side_effect = subprocess.TimeoutExpired(cmd="wifi-connect", timeout=10)
            mock_popen.return_value = proc
            from src.provisioning import run_provisioning
            run_provisioning("TestSSID", "testpass", timeout=10)
        proc.terminate.assert_called_once()

    def test_returns_false_when_binary_not_found(self):
        with patch("src.provisioning.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = FileNotFoundError()
            from src.provisioning import run_provisioning
            result = run_provisioning("TestSSID", "testpass", timeout=10)
        assert result is False
