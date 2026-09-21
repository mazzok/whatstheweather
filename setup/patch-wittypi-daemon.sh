#!/bin/bash
#
# patch-wittypi-daemon.sh — make WittyPi ignore spurious shutdown requests.
#
# Problem this solves
# -------------------
# Connecting USB-C to WittyPi's own power input while the Pi is running produces a
# burst of edges on GPIO-4 (the shutdown-request line) lasting 1-2.5 seconds. The
# MCU classifies that burst as a button click and daemon.sh, which blocks on
# `gpio -g wfi 4 falling` and shuts down on ANY falling edge regardless of reason,
# dutifully powers the Pi off. Net effect: plugging in the charger kills the Pi.
#
# Measured on hardware (WittyPi 4 L3V7, firmware ID 0x37, revision 0x07):
#   - unplugging USB-C:      no edges at all
#   - plugging USB-C in:     4-7 edges over 1.1-2.5s, ACTION_REASON = 0x03 (click)
#   - scheduled shutdown:    ACTION_REASON = 0x02 (alarm 2)
#
# Fix
# ---
# daemon.sh already reads ACTION_REASON after the edge — but only to log it. This
# patch makes it a gate: REASON_CLICK is logged and ignored (re-arming the wait),
# every other reason shuts down exactly as before.
#
# Trade-off: button-initiated shutdown stops working. This deployment never uses
# the button, and a charger that kills the Pi is the worse failure.
#
# Idempotent: safe to re-run, and must be re-run after a WittyPi software update
# (updates replace daemon.sh and revert this).
#
# Usage: bash setup/patch-wittypi-daemon.sh [/path/to/wittypi]

set -euo pipefail

WITTYPI_DIR="${1:-$HOME/wittypi}"
DAEMON="$WITTYPI_DIR/daemon.sh"
MARKER='# weatherpi: ignore spurious REASON_CLICK'

if [ ! -f "$DAEMON" ]; then
    echo "ERROR: $DAEMON not found. Pass the WittyPi directory as an argument." >&2
    exit 1
fi

if grep -qF "$MARKER" "$DAEMON"; then
    echo "Already patched: $DAEMON"
    exit 0
fi

ORIGINAL='gpio -g wfi $HALT_PIN falling'
if ! grep -qF "$ORIGINAL" "$DAEMON"; then
    echo "ERROR: expected line not found in $DAEMON:" >&2
    echo "  $ORIGINAL" >&2
    echo "WittyPi's daemon.sh has changed; re-check the patch before applying." >&2
    exit 1
fi

cp -a "$DAEMON" "$DAEMON.weatherpi-backup"

# Replace the single blocking wait with a loop that re-arms on REASON_CLICK.
# Written to a temp file and moved into place so a failure can't leave a
# half-written daemon.sh behind.
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

while IFS= read -r line; do
    if [ "$line" = "$ORIGINAL" ]; then
        cat <<'PATCH'
# weatherpi: ignore spurious REASON_CLICK
# Connecting USB-C bounces GPIO-4 for up to ~2.5s; the MCU reports that burst as a
# button click. Ignore it and keep waiting. All other shutdown reasons fall through.
while true; do
  gpio -g wfi $HALT_PIN falling
  if [ $has_mc == 1 ] ; then
    click_reason=$(i2c_read ${I2C_BUS} $I2C_MC_ADDRESS $I2C_ACTION_REASON)
    if [ "$click_reason" == $REASON_CLICK ]; then
      log 'Ignoring shutdown request: reason is CLICK (spurious GPIO-4 bounce on power connect).'
      continue
    fi
  fi
  break
done
PATCH
    else
        printf '%s\n' "$line"
    fi
done < "$DAEMON" > "$TMP"

cat "$TMP" > "$DAEMON"

echo "Patched: $DAEMON (backup at $DAEMON.weatherpi-backup)"
echo "Restart the daemon to apply:  sudo systemctl restart wittypi.service"
