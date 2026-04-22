"""renderer.py — Compose full 800x480 e-ink display image using Pillow."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.icons import draw_icon
from src.weather import WeatherData, DayForecast

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

STATUS_BAR_H = 30
WEATHER_SECTION_H = 135
CHART_MARGIN_LEFT = 40
CHART_MARGIN_RIGHT = 42
SIDE_PADDING = 30

BLACK = 0
GRAY = 160
WHITE = 255

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# Font paths relative to project root
_PROJECT_ROOT = Path(__file__).parent.parent
_FONT_REGULAR = str(_PROJECT_ROOT / "fonts" / "DejaVuSansMono.ttf")
_FONT_BOLD = str(_PROJECT_ROOT / "fonts" / "DejaVuSansMono-Bold.ttf")


def _load_font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    path = _FONT_BOLD if bold else _FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_display(
    weather: WeatherData,
    battery_pct: float,
    off_grid_days: int,
    error: str = "",
    city: str = "",
) -> Image.Image:
    """Compose and return the full 800x480 grayscale display image."""
    # Use 245 (slightly off-white, matching e-ink paper tone) so the background
    # is visually white but distinct from drawn whites where needed.
    img = Image.new("L", (DISPLAY_WIDTH, DISPLAY_HEIGHT), 245)
    draw = ImageDraw.Draw(img)

    y = 0
    _draw_status_bar(draw, y, battery_pct, off_grid_days, error or weather.error, city)
    y += STATUS_BAR_H

    _draw_weather_section(draw, img, y, weather)
    y += WEATHER_SECTION_H

    _draw_chart(draw, img, y, weather)

    return img


# ---------------------------------------------------------------------------
# Status bar
# ---------------------------------------------------------------------------

def _draw_status_bar(
    draw: ImageDraw.Draw,
    y: int,
    battery_pct: float,
    off_grid_days: int,
    error: str,
    city: str,
) -> None:
    font = _load_font(False, 14)

    # Left: uptime or error
    if error:
        text = f"Fehler: {error}"
    else:
        text = f"Off grid: {off_grid_days} days"
    draw.text((16, y + 6), text, fill=BLACK, font=font)

    # Right: battery icon
    # Battery body: 28×14 at right edge
    bx = DISPLAY_WIDTH - 16 - 28 - 4  # leave room for terminal nub
    by = y + (STATUS_BAR_H - 14) // 2

    # City name (left of battery)
    if city:
        city_font = _load_font(False, 14)
        city_bbox = draw.textbbox((0, 0), city, font=city_font)
        city_w = city_bbox[2] - city_bbox[0]
        city_x = bx - 8 - city_w
        draw.text((city_x, y + 6), city, fill=BLACK, font=city_font)
    bw, bh = 28, 14
    draw.rectangle([bx, by, bx + bw, by + bh], outline=BLACK, width=2)
    # Terminal nub (3×7 centred on right edge)
    nub_w, nub_h = 3, 7
    draw.rectangle(
        [bx + bw, by + (bh - nub_h) // 2, bx + bw + nub_w, by + (bh + nub_h) // 2],
        fill=BLACK,
    )
    # Fill bar
    fill_w = max(0, int((bw - 4) * battery_pct / 100))
    if fill_w > 0:
        draw.rectangle([bx + 2, by + 2, bx + 2 + fill_w, by + bh - 2], fill=BLACK)

    # Separator line
    draw.line([(0, y + STATUS_BAR_H - 1), (DISPLAY_WIDTH, y + STATUS_BAR_H - 1)], fill=BLACK, width=2)


# ---------------------------------------------------------------------------
# Current weather section
# ---------------------------------------------------------------------------

def _draw_weather_section(
    draw: ImageDraw.Draw,
    img: Image.Image,
    y: int,
    weather: WeatherData,
) -> None:
    """Draw the 135px tall current-weather band."""
    section_bottom = y + WEATHER_SECTION_H

    # --- LEFT: weather icon (90x90) + temp + desc + minmax ---
    icon_x = SIDE_PADDING
    icon_y = y + (WEATHER_SECTION_H - 90) // 2
    draw_icon(draw, weather.current_icon, icon_x, icon_y, 90, BLACK)

    # Temperature number
    font_temp_big = _load_font(True, 56)
    font_temp_unit = _load_font(False, 24)
    font_desc = _load_font(False, 20)
    font_minmax = _load_font(False, 16)

    temp_x = icon_x + 90 + 16
    temp_str = f"{int(round(weather.current_temp))}"
    draw.text((temp_x, y + 10), temp_str, fill=BLACK, font=font_temp_big)
    # Measure width to place °C right after
    bbox = draw.textbbox((temp_x, y + 10), temp_str, font=font_temp_big)
    unit_x = bbox[2] + 4
    draw.text((unit_x, y + 20), "°C", fill=BLACK, font=font_temp_unit)

    # Description
    draw.text((temp_x, y + 72), weather.current_desc, fill=BLACK, font=font_desc)

    # Min/max to the right of the big temp
    minmax_x = unit_x + 40
    draw.text((minmax_x, y + 14), f"{int(round(weather.temp_max_today))}°C", fill=BLACK, font=font_minmax)
    draw.text((minmax_x, y + 36), f"{int(round(weather.temp_min_today))}°C", fill=BLACK, font=font_minmax)

    # --- VERTICAL DIVIDER ---
    divider_x = DISPLAY_WIDTH // 2 + 20
    draw.line([(divider_x, y + 12), (divider_x, section_bottom - 12)], fill=BLACK, width=2)

    # --- RIGHT: wind + precip ---
    right_x = divider_x + 24
    info_y_wind = y + 20
    info_y_rain = y + 75

    # Wind icon (32x32)
    draw_icon(draw, "windy", right_x, info_y_wind, 32, BLACK)
    font_info = _load_font(True, 22)
    draw.text((right_x + 42, info_y_wind + 4), f"{int(round(weather.wind_speed))} km/h | {weather.wind_direction}", fill=BLACK, font=font_info)

    # Rain/precip icon (32x32)
    draw_icon(draw, "rain", right_x, info_y_rain, 32, BLACK)
    draw.text((right_x + 42, info_y_rain + 4), f"{int(round(weather.precip_probability))} %", fill=BLACK, font=font_info)

    # Bottom border of section
    draw.line([(0, section_bottom - 1), (DISPLAY_WIDTH, section_bottom - 1)], fill=BLACK, width=3)


# ---------------------------------------------------------------------------
# Temperature trend chart
# ---------------------------------------------------------------------------

def _draw_chart(
    draw: ImageDraw.Draw,
    img: Image.Image,
    y_start: int,
    weather: WeatherData,
) -> None:
    """Draw the weekly temperature trend chart."""
    font_small = _load_font(False, 11)
    font_avg = _load_font(True, 22)       # was 15, then 19
    font_yaxis = _load_font(True, 19)     # was 15

    # Layout
    chart_left = SIDE_PADDING + CHART_MARGIN_LEFT
    chart_right = DISPLAY_WIDTH - SIDE_PADDING - CHART_MARGIN_RIGHT
    chart_width = chart_right - chart_left

    # X-axis label area height at bottom
    label_area_h = 52
    chart_top = y_start + 14           # small top padding
    chart_bottom = DISPLAY_HEIGHT - label_area_h - 4
    chart_height = chart_bottom - chart_top

    # --- Determine the 7-day window: Monday of current week ---
    today = date.today()
    # Find this week's Monday
    monday = today - timedelta(days=today.weekday())
    week_dates = [monday + timedelta(days=i) for i in range(7)]

    # Map DayForecast entries by date
    forecast_by_date: dict[date, DayForecast] = {d.date: d for d in weather.week}

    # Collect data points for all 7 days
    points: list[tuple[date, float, float, float, str] | None] = []
    for d in week_dates:
        fc = forecast_by_date.get(d)
        if fc is not None:
            points.append((d, fc.temp_min, fc.temp_max, fc.temp_avg, fc.icon))
        else:
            points.append(None)

    # Dynamic Y-axis scaling
    all_temps: list[float] = []
    for p in points:
        if p:
            all_temps.extend([p[1], p[2], p[3]])
    if not all_temps:
        return

    temp_min_global = min(all_temps)
    temp_max_global = max(all_temps)
    # Add a little padding
    temp_range = max(temp_max_global - temp_min_global, 1.0)
    t_lo = temp_min_global - temp_range * 0.08
    t_hi = temp_max_global + temp_range * 0.08

    def temp_to_y(t: float) -> int:
        frac = (t - t_lo) / (t_hi - t_lo)
        return int(chart_bottom - frac * chart_height)

    # X positions for each day (evenly spaced, centred in columns)
    col_w = chart_width / 7
    def day_x(i: int) -> int:
        return int(chart_left + (i + 0.5) * col_w)

    # --- Draw chart axes ---
    draw.line([(chart_left, chart_top), (chart_left, chart_bottom)], fill=BLACK, width=2)
    draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=BLACK, width=2)

    # Y-axis labels: top, mid, bottom
    y_top_temp = round(t_hi)
    y_mid_temp = round((t_hi + t_lo) / 2)
    y_bot_temp = round(t_lo)
    for temp_val, ypos in [
        (y_top_temp, chart_top),
        (y_mid_temp, temp_to_y((t_hi + t_lo) / 2)),
        (y_bot_temp, chart_bottom),
    ]:
        label = f"{int(temp_val)}°"
        bbox = draw.textbbox((0, 0), label, font=font_yaxis)
        lw = bbox[2] - bbox[0]
        draw.text((chart_left - lw - 4, ypos - 6), label, fill=BLACK, font=font_yaxis)

    # Grid lines (dashed-ish: draw short segments)
    for ypos in [chart_top, temp_to_y((t_hi + t_lo) / 2), chart_bottom]:
        x = chart_left
        while x < chart_right:
            draw.line([(x, ypos), (min(x + 4, chart_right), ypos)], fill=180, width=1)
            x += 8

    # --- Classify each day as past / today / future ---
    # today index within the 7-day window
    today_idx: int | None = None
    for i, d in enumerate(week_dates):
        if d == today:
            today_idx = i
            break

    def _is_past(i: int) -> bool:
        if today_idx is None:
            return False
        return i < today_idx

    def _is_today(i: int) -> bool:
        return i == today_idx

    # --- Collect (x, y_avg) for valid points to draw lines ---
    avg_positions: list[tuple[int, int, int, bool]] = []  # (i, px, py, is_past)
    for i, p in enumerate(points):
        if p is not None:
            px = day_x(i)
            py = temp_to_y(p[3])
            avg_positions.append((i, px, py, _is_past(i)))

    # Draw connecting lines in two passes:
    # 1) Gray line from first valid past point through last past point AND to today
    # 2) Black line from today onwards

    past_pts = [(px, py) for i, px, py, is_p in avg_positions if is_p]
    today_pt = next(((px, py) for i, px, py, _ in avg_positions if _is_today(i)), None)
    future_pts = [(px, py) for i, px, py, _ in avg_positions if not _is_past(i) and not _is_today(i)]

    # Gray segment: past + bridge to today
    gray_line = past_pts[:]
    if today_pt:
        gray_line.append(today_pt)
    if len(gray_line) >= 2:
        draw.line(gray_line, fill=GRAY, width=2)

    # Black segment: today + future
    black_line = []
    if today_pt:
        black_line.append(today_pt)
    black_line.extend(future_pts)
    if len(black_line) >= 2:
        draw.line(black_line, fill=BLACK, width=3)

    # --- Draw circles and mini icons ---
    for i, p in enumerate(points):
        if p is None:
            continue
        px = day_x(i)
        py = temp_to_y(p[3])
        is_past = _is_past(i)
        is_today_flag = _is_today(i)

        dot_color = GRAY if is_past else BLACK
        r = 13 if is_today_flag else 8    # was 9 if today, 8 otherwise

        # Draw circle (filled)
        draw.ellipse([px - r, py - r, px + r, py + r], fill=dot_color)

        # Small weather icon (24x24) above the dot
        icon_sz = 24
        icon_x = px - icon_sz // 2
        icon_y = py - r - icon_sz - 2
        draw_icon(draw, p[4], icon_x, icon_y, icon_sz, dot_color)

    # --- X-axis labels ---
    label_y = chart_bottom + 8
    for i, (d, p) in enumerate(zip(week_dates, points)):
        if p is None:
            # Draw date with no temp info
            px = day_x(i)
            is_past = _is_past(i)
            lbl_color = GRAY if is_past else BLACK
            wd = WEEKDAYS[d.weekday()]
            bbox = draw.textbbox((0, 0), wd, font=font_small)
            lw = bbox[2] - bbox[0]
            draw.text((px - lw // 2, label_y), wd, fill=lbl_color, font=font_small)
            continue

        d_val, t_min, t_max, t_avg, icon = p
        is_past = _is_past(i)
        is_today_flag = _is_today(i)
        lbl_color = GRAY if is_past else BLACK

        px = day_x(i)
        wd = WEEKDAYS[d.weekday()]

        # Row 1: weekday name (centred)
        bbox = draw.textbbox((0, 0), wd, font=font_small)
        lw = bbox[2] - bbox[0]
        draw.text((px - lw // 2, label_y), wd, fill=lbl_color, font=font_small)

        # Row 2: min° avg° max° — small-bold-small
        min_str = f"{int(round(t_min))}°"
        avg_str = f"{int(round(t_avg))}°"
        max_str = f"{int(round(t_max))}°"

        min_bbox = draw.textbbox((0, 0), min_str, font=font_small)
        avg_bbox = draw.textbbox((0, 0), avg_str, font=font_avg)
        max_bbox = draw.textbbox((0, 0), max_str, font=font_small)

        min_w = min_bbox[2] - min_bbox[0]
        avg_w = avg_bbox[2] - avg_bbox[0]
        max_w = max_bbox[2] - max_bbox[0]

        gap = 2
        total_w = min_w + gap + avg_w + gap + max_w
        tx = px - total_w // 2

        row2_y = label_y + 13
        draw.text((tx, row2_y + 3), min_str, fill=lbl_color, font=font_small)
        tx += min_w + gap
        draw.text((tx, row2_y), avg_str, fill=lbl_color, font=font_avg)
        tx += avg_w + gap
        draw.text((tx, row2_y + 3), max_str, fill=lbl_color, font=font_small)

        # Row 3: date dd.mm
        date_str = f"{d.day:02d}.{d.month:02d}"
        date_bbox = draw.textbbox((0, 0), date_str, font=font_small)
        dw = date_bbox[2] - date_bbox[0]
        row3_y = row2_y + 18
        draw.text((px - dw // 2, row3_y), date_str, fill=lbl_color, font=font_small)


# ---------------------------------------------------------------------------
# CLI preview
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import date as _date

    parser = argparse.ArgumentParser(description="Generate a renderer preview image")
    parser.add_argument("--preview", default="preview.png", help="Output PNG file path")
    args = parser.parse_args()

    # Build sample data matching the mockup
    _today = _date(2026, 4, 17)
    _week = [
        DayForecast(date=_date(2026, 4, 14), temp_min=5, temp_max=18, temp_avg=12, icon="overcast"),
        DayForecast(date=_date(2026, 4, 15), temp_min=7, temp_max=20, temp_avg=14, icon="rain"),
        DayForecast(date=_date(2026, 4, 16), temp_min=8, temp_max=22, temp_avg=16, icon="partly_cloudy"),
        DayForecast(date=_date(2026, 4, 17), temp_min=10, temp_max=25, temp_avg=19, icon="clear"),
        DayForecast(date=_date(2026, 4, 18), temp_min=9, temp_max=23, temp_avg=17, icon="mostly_cloudy"),
        DayForecast(date=_date(2026, 4, 19), temp_min=8, temp_max=24, temp_avg=18, icon="overcast"),
        DayForecast(date=_date(2026, 4, 20), temp_min=7, temp_max=21, temp_avg=16, icon="rain"),
    ]
    _weather = WeatherData(
        current_temp=23, current_icon="clear", current_desc="Sonnig",
        wind_speed=12, wind_direction="NW", precip_probability=10,
        temp_min_today=10, temp_max_today=25,
        week=_week, timestamp="2026-04-17T10:00:00",
    )

    img = render_display(_weather, battery_pct=78, off_grid_days=2450, city="Wien")
    img.save(args.preview)
    print(f"Preview saved to {args.preview}")
