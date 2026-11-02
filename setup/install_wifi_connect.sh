#!/bin/bash
# setup/install_wifi_connect.sh
# Installs Balena WiFi Connect binary for Raspberry Pi (ARMv6/ARMv7).
# Run once on the Pi: sudo bash setup/install_wifi_connect.sh
set -euo pipefail

ARCH=$(uname -m)
case "$ARCH" in
  armv7l)  TARBALL="wifi-connect-armv7-unknown-linux-gnueabihf.tar.gz" ;;
  aarch64) TARBALL="wifi-connect-aarch64-unknown-linux-gnu.tar.gz" ;;
  *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

BASE_URL="https://github.com/balena-os/wifi-connect/releases/latest/download"
# wifi-connect finds its captive-portal page here when run from /usr/local/sbin
UI_DIR="/usr/local/share/wifi-connect/ui"
TMP=$(mktemp -d)

echo "Downloading $TARBALL..."
curl -fsSL "$BASE_URL/$TARBALL" | tar -xz -C "$TMP"

install -m 755 "$TMP/wifi-connect" /usr/local/sbin/wifi-connect

echo "Downloading captive portal UI..."
rm -rf "$UI_DIR"
mkdir -p "$UI_DIR"
curl -fsSL "$BASE_URL/wifi-connect-ui.tar.gz" | tar -xz -C "$UI_DIR"
rm -rf "$TMP"

echo "Installed: $(wifi-connect --version)"
echo "Done."
