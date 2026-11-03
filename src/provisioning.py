# src/provisioning.py
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

_PROJECT_ROOT = Path(__file__).parent.parent
_FONT_BOLD = str(_PROJECT_ROOT / "fonts" / "Inter-Bold.ttf")

BLACK = 0
WHITE = 255
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

logger = logging.getLogger(__name__)

# Why the last run_provisioning() returned False; shown on the error screen.
last_error = ""


def run_provisioning(ssid: str, password: str, timeout: int = 900) -> bool:
    """Start Balena WiFi Connect and wait for successful network configuration.

    Returns True if the user configured WiFi within `timeout` seconds.
    Returns False on timeout or if the wifi-connect binary is not found;
    `last_error` then holds a short German reason.
    """
    global last_error
    last_error = ""
    try:
        proc = subprocess.Popen(
            ["sudo", "wifi-connect", "--portal-ssid", ssid, "--portal-passphrase", password]
        )
    except FileNotFoundError:
        logger.error("wifi-connect binary not found at /usr/local/sbin/wifi-connect")
        last_error = "wifi-connect fehlt"
        return False

    try:
        rc = proc.wait(timeout=timeout)
        if rc != 0:
            logger.error("wifi-connect exited with code %d", rc)
            last_error = f"wifi-connect Exit {rc}"
            return False
        logger.info("wifi-connect exited — network configured")
        return True
    except subprocess.TimeoutExpired:
        logger.warning("Provisioning timed out after %ds", timeout)
        last_error = "Zeitüberschreitung"
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return False


def render_provisioning_screen(
    ssid: str, password: str, update_display_fn: callable
) -> None:
    """Render a QR code provisioning screen on the e-ink display.

    The QR code encodes WiFi credentials for the Pi's own hotspot so a
    smartphone can connect automatically and open the captive portal.
    """
    # Build QR code image
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(f"WIFI:T:WPA;S:{ssid};P:{password};;")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("L")
    qr_w, qr_h = qr_img.size

    # Compose display image
    image = Image.new("L", (DISPLAY_WIDTH, DISPLAY_HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)

    try:
        font_title = ImageFont.truetype(_FONT_BOLD, 28)
        font_body = ImageFont.truetype(_FONT_BOLD, 22)
        font_small = ImageFont.truetype(_FONT_BOLD, 18)
    except OSError:
        font_title = font_body = font_small = ImageFont.load_default()

    # Title
    title = "Kein WiFi konfiguriert"
    title_w = draw.textlength(title, font=font_title)
    draw.text(((DISPLAY_WIDTH - title_w) / 2, 30), title, fill=BLACK, font=font_title)

    # QR code (centered)
    qr_x = (DISPLAY_WIDTH - qr_w) // 2
    qr_y = 80
    image.paste(qr_img, (qr_x, qr_y))

    # Instructions below QR code
    line1 = "Scanne um WiFi einzurichten"
    line2 = f"oder verbinde mit \"{ssid}\""
    line3 = "dann öffne  192.168.42.1"

    y = qr_y + qr_h + 20
    for line, font in [(line1, font_body), (line2, font_small), (line3, font_small)]:
        w = draw.textlength(line, font=font)
        draw.text(((DISPLAY_WIDTH - w) / 2, y), line, fill=BLACK, font=font)
        y += 34

    update_display_fn(image)
    logger.info("Provisioning screen rendered (SSID: %s)", ssid)
