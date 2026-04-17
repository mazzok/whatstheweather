# E-Ink Weather Display — Design Spec

## Overview

A Raspberry Pi Zero 2 W-based weather station that fetches weather data from GeoSphere Austria every 2 hours and renders it on a 7.5" Waveshare E-Ink display (800x480, black/white). The device runs on battery (3.7V 5200mAh HAT) and enters deep sleep between updates to maximize battery life.

## Hardware

- **Board:** Raspberry Pi Zero 2 W
- **Display:** Waveshare 7.5" E-Paper (800x480, black/white)
- **Power:** Battery HAT, 3.7V / 5200mAh LiPo
- **Language:** Python

## Display Layout (800x480)

### Status Bar (top, ~30px)
- Left: "Up since: X days" (uptime counter from persistent file storing first-start date)
- Right: Battery icon (graphical fill indicator)

### Current Weather Section (~135px)
Split by a vertical divider line:

**Left side:**
- Large weather icon (SVG-style, ~90x90px)
- Current temperature large ("23 °C"), number and unit visually separated
- Weather description below ("Sonnig")
- Min/Max temperature to the right of the main temperature (smaller, stacked: "31°C" / "10°C")

**Right side:**
- Wind: icon + speed (km/h) + direction (e.g., "12 km/h | NW")
- Precipitation probability: rain-cloud icon + percentage (e.g., "10 %")

### Temperature Trend Chart (remaining space, ~315px)
- X-axis: Monday through Sunday (Mo–So), always showing the full current week
- Y-axis: Temperature in °C, dynamically scaled based on weekly min/max, labels in same font size/weight as X-axis
- Data line: Average daily temperature plotted as a line chart with circular data points
- Past days (before today): gray line, gray circles (r=8)
- Today: black circle, slightly larger (r=9)
- Future days: black line, black circles (r=8)
- The connecting line from last past day to today is gray
- Weather icons: small (~24x24px) weather symbol above each data point
- Equal left/right margins for the chart area
- Below each data point on X-axis (vertically aligned with the data point):
  - Weekday label (e.g., "Do")
  - Temperature trio: `Min° **Avg°** Max°` (min and max in small font, avg in larger bold font)
  - Date (e.g., "17.04")
- No chart title needed (self-explanatory)
- No special marker for today (first black entry is implicitly today)

## Weather Icons (18 types)

All icons rendered as simple black line/fill drawings suitable for 1-bit E-Ink display. Must be recognizable at ~24x24px (chart size) and ~90x90px (main display).

### Sky Conditions
1. **clear** — Sun with rays
2. **partly_cloudy** — Sun with cloud overlay
3. **mostly_cloudy** — Large cloud, small sun sliver
4. **overcast** — Full cloud, no sun
5. **fog** — Horizontal stacked lines

### Rain
6. **drizzle** — Cloud + 2 short rain lines
7. **rain** — Cloud + 3 rain lines
8. **heavy_rain** — Cloud + 4 bold rain lines
9. **freezing_rain** — Cloud + rain lines + ice crystal
10. **rain_shower** — Cumulus-shaped cloud + 3 rain lines

### Snow
11. **light_snow** — Cloud + 2 snowflakes (asterisk shape)
12. **snow** — Cloud + 3 snowflakes
13. **heavy_snow** — Cloud + 4 snowflakes
14. **sleet** — Cloud + rain lines + snowflake

### Thunderstorms & Wind
15. **thunderstorm** — Cloud + lightning bolt
16. **thunderstorm_rain** — Cloud + lightning bolt + rain lines
17. **thunderstorm_hail** — Cloud + lightning bolt + hail circles
18. **windy** — Stylized curved wind lines

## Architecture

```
[Cron/Timer] → [main.py] → [IP Geolocation] → lat/lon
                    ↓
              [GeoSphere API] → Weather data (current + 7-day)
                    ↓
              [Renderer (Pillow)] → 800x480 image
                    ↓
              [Waveshare Driver] → E-Ink display update
                    ↓
              [Deep Sleep]
```

### Modules

| Module | Responsibility |
|--------|---------------|
| `location.py` | IP geolocation → lat/lon (via ip-api.com or similar) |
| `weather.py` | GeoSphere Austria API calls (current + forecast + historical) |
| `renderer.py` | Pillow-based rendering of the 800x480 display image |
| `display.py` | Waveshare E-Ink driver wrapper |
| `battery.py` | Battery status readout from HAT |
| `main.py` | Orchestration: wake → fetch data → render → display → sleep |

Modules are separate files but invoked from a single `main.py` entry point. This structure allows easy migration to a more modular service architecture later if needed.

### Update Cycle (every 2 hours)

1. Pi wakes up (RTC/Timer or systemd timer)
2. Connect to WLAN
3. IP → determine location (lat/lon)
4. Fetch data from GeoSphere API: current weather + 7-day forecast
5. Read battery status from HAT
6. Render image (Pillow → 800x480 black/white)
7. Update E-Ink display
8. Enter deep sleep (or stay awake in debug mode)

## GeoSphere Austria API Integration

**Base URL:** `https://dataset.api.hub.geosphere.at`

### Endpoints Used

| Purpose | Endpoint | Key Parameters |
|---------|----------|---------------|
| Current weather | `/v1/station/current/tawes-v1-10min` | Nearest station to lat/lon |
| 7-day forecast | `/v1/timeseries/forecast/nwp-v1-1h-2500m` | `t2m`, `mnt2m`, `mxt2m`, `sy`, `rr_acc`, `u10m`, `v10m` |
| Historical (past days) | `/v1/station/historical/klima-v2-1d` | For days earlier in the week that fall outside forecast range |

### Data Processing

- **Daily aggregation:** From hourly forecast data, compute per-day min, max, and average temperature
- **Weather symbol:** Dominant `sy` code during daylight hours (6:00–20:00) per day
- **Wind:** Current values from `u10m`/`v10m` → speed (km/h) + compass direction
- **Precipitation probability:** Derived from hourly forecast precipitation data
- **Past days:** Cache last known values; for days outside forecast range, use historical station data (`klima-v2-1d`)

### API Constraints

- No API key required (CC BY 4.0 license)
- Rate limits: 5 req/s, 240 req/h (more than sufficient for 2h interval)

### Caching

- Weather data cached locally as JSON (`~/.weather_cache.json`)
- On API error: display last cached data + error indicator in status bar

## Configuration

```yaml
# config.yaml
debug: true      # false = deep sleep after update, true = Pi stays awake
interval: 7200   # seconds between updates (only relevant in debug mode)
```

- `debug: true` → Pi stays awake, next update via `sleep()` or manual trigger. Logging to stdout.
- `debug: false` → Pi shuts down after display update (production mode). Logging to file only.

## Deep Sleep & Power Management

- **Production:** `systemd` timer triggers `main.py` every 2 hours. After display update: `sudo shutdown -h now` or `rtcwake` for hardware sleep. Alternatively: UPS HAT watchdog timer to wake Pi after 2h.
- **Debug:** Pi stays on, uses `time.sleep(interval)` or waits for manual invocation.
- **Uptime counter:** Persistent file stores first-start date, "Up since: X days" computed on each wake.

## Error Handling

- **No WLAN:** Display last cached data, show "Offline" in status bar
- **API error:** Display last cached data, show timestamp of last successful update in status bar
- **Battery critical (<10%):** Display warning on screen

## Visual Reference

Reference mockups are stored in `docs/mockups/`:

| File | Purpose |
|------|---------|
| `layout-display.html` | Full display layout mockup (E-Ink simulation, 800x480) |
| `weather-icons-full-size.html` | All 18 weather icons at full size (~80x80px) |
| `weather-icons-chart-size.html` | All 18 weather icons at chart size (~24x24px) |

These HTML files serve as the pixel-level reference for the Pillow renderer. The `renderer.py` module must include a `--preview` mode that outputs a PNG for visual comparison against these mockups.

Layout constants derived from the mockup:

| Element | Value |
|---------|-------|
| Status bar height | 30px |
| Weather section height | 135px |
| Chart left/right margin | 40px / 42px |
| Main temperature font size | 56px |
| Y-axis / X-axis label font size | 15px bold |
| Min/Max font size | 10px |
| Avg font size | 15px bold |
| Data point radius (past) | 8px |
| Data point radius (today) | 9px |
| Data point radius (future) | 8px |
| Chart weather icon size | ~24x24px |
| Main weather icon size | ~90x90px |

## Language

- All UI text in German (weekdays: Mo, Di, Mi, Do, Fr, Sa, So; weather descriptions in German)
