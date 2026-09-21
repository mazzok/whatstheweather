# Handover: WittyPi charging detection — RESOLVED (pending hardware verification)

**Date:** 2026-09-21 (continues sessions from 2026-09-17/18)
**Status:** Root cause found, fix implemented, unit-tested. **Hardware verification still
outstanding** — see "Remaining verification" at the bottom before re-enabling the service.

## Summary

Two independent defects, not one. The first made charging undetectable; the second made
connecting the charger shut the Pi down. Both are fixed.

### Defect 1 — wrong signal, and the old evidence was misread

`is_charging()` read `CHRG_PIN` (GPIO 5). On this unit that pin reads a constant `1`
regardless of input, so the function was permanently `False`, and its Vout fallback never
ran because the GPIO read *succeeded* — it just returned a meaningless value.

The earlier session had also read I2C register `0x07` (`I2C_POWER_MODE`), got `0x00` with
USB-C connected, and concluded "battery mode". **That polarity was inverted.** `0x00` means
*external power*. The register was correct all along; the interpretation wasn't. The blue
charging LED the user observed was telling the truth, and the "unresolved contradiction"
recorded in the previous version of this document was simply that misreading.

Established by diffing the full register block (`0x00`–`0x3F`) plus GPIO 4/5/6 between
plugged and unplugged states — the test nobody had run, because every prior attempt sampled
one state at a time.

| Signal | Plugged | Unplugged |
|---|---|---|
| reg `0x07` (power mode) | `0x00` | `0x02` |
| reg `0x01`/`0x02` (Vin) | 4.73 V | 4.12 V |
| reg `0x3A`/`0x3B` | `0xc1`/`0x30` | `0xb1`/`0x31` |
| GPIO 5/6 (`CHRG`/`STDBY`) | `1`/`1` | `1`/`1` |

Vin also moves, but only 0.6 V apart and the unplugged reading tracks battery voltage — a
threshold there would drift as the cell drains. Register `0x07` is binary and
battery-independent, so that's the signal.

Note it reports power *source*, not charge activity. It stays `0x00` once a full battery
stops drawing current — which is the behavior we want (stay awake while plugged in). A true
charge-detect signal would drop out at full battery and return the Pi to the shutdown grid
while still connected. The broken signal was also the wrong signal.

### Defect 2 — plugging in the charger shut the Pi down

Connecting USB-C bounces GPIO-4 (WittyPi's shutdown-request line) for 1–2.5 s: 4–7 edges,
varying per plug-in. Unplugging produces none. WittyPi's MCU classifies that burst as a
button click (`ACTION_REASON = 0x03`), and `daemon.sh` — which blocks on
`gpio -g wfi 4 falling` and shuts down on any falling edge, reading `ACTION_REASON` only to
log it — powers the Pi off.

Confirmed by killing `daemon.sh` and its `gpio wfi` child: with nothing watching GPIO-4, the
Pi survives plug-in indefinitely. So this was never a hardware power cut, an undervoltage
trip, or a current-budget problem (`Vout=5.26 V, Iout=0.21 A` at boot, low-voltage cutoff
never fired).

Kernel edge logs undercount the burst — only rising edges surfaced and timestamps came back
out of order, indicating FIFO overflow. So "2.5 s" is a floor, not a ceiling. That ruled out
a timing-based debounce: no window can be proven long enough.

### Defect 3 (configuration, not a bug)

`I2C_CONF_DEFAULT_ON` (reg 17) read `0x00` — disabled, despite README step 2 calling for it.
Plugging into a sleeping Pi did nothing until the next startup alarm, up to 2 h later.

## Fix

1. **`src/wittypi.py`** — `is_charging()` reads `REG_POWER_MODE` (`0x07`) via the existing
   SMBus handle and returns `True` on `0x00`. GPIO `CHRG_PIN` path and the Vout fallback
   deleted; no bus or a read error returns `False`, which selects the normal schedule whose
   hard shutdown protects the battery.
2. **`setup/patch-wittypi-daemon.sh`** — patches `daemon.sh` to gate on `ACTION_REASON`
   instead of logging it: `REASON_CLICK` is logged and ignored (re-arming the wait), every
   other reason shuts down unchanged. Idempotent, backs up the original, and **must be
   re-run after any WittyPi software update**. Costs button-initiated shutdown, which this
   deployment doesn't use.
3. **`DEFAULT_ON`** — `sudo i2cset -y 1 0x08 17 0x01`, documented in README step 2.

Nothing changed in `reconcile_schedule()`, `_apply_schedule()`, the `.wpi` files, or
`main.py`. That machinery was always correct and was only ever starved of a true signal.

113/113 unit tests pass.

## Remaining verification (on hardware, before trusting this)

1. **Plug in while running** → Pi survives; `~/wittypi/wittyPi.log` shows the ignored click.
2. **Plug in while off** → boots, `~/wittypi/schedule.wpi` becomes the `WAIT` variant, log
   shows "Skip scheduling next shutdown".
3. **Unplug** → next boot restores `weatherpi.wpi`.
4. **A real scheduled shutdown still fires.** This is the regression the reason-gate could
   plausibly break, and it's the one that matters for off-grid operation. Test it
   explicitly; don't assume.

Only after 4 passes should `weather-display.service` be re-enabled:

```bash
sudo systemctl enable weather-display.service
sudo systemctl start weather-display.service
```

## Known limitation

`main.py:149` samples `is_charging()` once at startup. Hot-plugging while the app is
mid-run won't switch it into charging mode — the Pi renders and shuts down as usual, then
`DEFAULT_ON` immediately boots it back up (USB-C is still connected), and *that* boot enters
charging mode. The outcome is correct; it costs one extra boot cycle. Left as-is rather than
adding a mid-run poll, since the Pi is only awake ~5 min per 2 h cycle.

## Worth doing separately

A 1–2.5 s bounce burst on the shutdown line at power connect looks like a board defect.
Worth reporting to UUGear (firmware ID `0x37`, revision `0x07`, WittyPi 4 L3V7) — they may
have a firmware fix that beats patching `daemon.sh` after every update.
