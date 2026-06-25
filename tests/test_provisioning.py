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


from PIL import Image


class TestRenderProvisioningScreen:
    def test_calls_display_function_once(self):
        from src.provisioning import render_provisioning_screen
        calls = []
        render_provisioning_screen("TestNet", "pass123", lambda img: calls.append(img))
        assert len(calls) == 1

    def test_passes_pil_image_to_display_fn(self):
        from src.provisioning import render_provisioning_screen
        captured = []
        render_provisioning_screen("TestNet", "pass123", lambda img: captured.append(img))
        assert isinstance(captured[0], Image.Image)

    def test_image_has_correct_dimensions(self):
        from src.provisioning import render_provisioning_screen
        captured = []
        render_provisioning_screen("TestNet", "pass123", lambda img: captured.append(img))
        assert captured[0].size == (800, 480)

    def test_image_is_grayscale(self):
        from src.provisioning import render_provisioning_screen
        captured = []
        render_provisioning_screen("TestNet", "pass123", lambda img: captured.append(img))
        assert captured[0].mode == "L"

    def test_qr_encodes_wifi_payload(self):
        from src.provisioning import render_provisioning_screen
        with patch("src.provisioning.qrcode.QRCode") as mock_qr_cls:
            mock_qr = MagicMock()
            mock_qr_cls.return_value = mock_qr
            # make_image returns something with .convert() that returns a valid Image
            mock_qr.make_image.return_value = MagicMock(
                convert=MagicMock(return_value=Image.new("L", (200, 200), 255))
            )
            render_provisioning_screen("MyNet", "mypass", lambda img: None)
        mock_qr.add_data.assert_called_once_with("WIFI:T:WPA;S:MyNet;P:mypass;;")
