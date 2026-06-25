#!/bin/bash
# setup/install_wifi_connect.sh
# Installs Balena WiFi Connect binary for Raspberry Pi (ARMv6/ARMv7).
# Run once on the Pi: sudo bash setup/install_wifi_connect.sh
set -euo pipefail

ARCH=$(uname -m)
case "$ARCH" in
  armv6l)  TARBALL="wifi-connect-armv6l.tar.gz" ;;
  armv7l)  TARBALL="wifi-connect-armv7hf.tar.gz" ;;
  aarch64) TARBALL="wifi-connect-aarch64.tar.gz" ;;
  *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

BASE_URL="https://github.com/balena-io/wifi-connect/releases/latest/download"
TMP=$(mktemp -d)

echo "Downloading $TARBALL..."
curl -fsSL "$BASE_URL/$TARBALL" | tar -xz -C "$TMP"

install -m 755 "$TMP/wifi-connect" /usr/local/sbin/wifi-connect
rm -rf "$TMP"

echo "Installed: $(wifi-connect --version)"
echo "Done."
