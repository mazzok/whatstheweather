"""renderer.py — Compose full 800x480 e-ink display image using Pillow."""

from __future__ import annotations

import argparse
import math
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
WEATHER_SECTION_H = 175
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
    city: str = "",
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
        city_font = _load_font(True, 14)
        city_bbox = draw.textbbox((0, 0), city, font=city_font)
        city_w = city_bbox[2] - city_bbox[0]
        city_h = city_bbox[3] - city_bbox[1]
        city_x = bx - 8 - city_w
        battery_center_y = by + 14 // 2
        city_y = battery_center_y - city_h // 2
        draw.text((city_x, city_y), city, fill=BLACK, font=city_font)

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
    """Draw the weather band: temp+icons left, date+wind right."""
    section_bottom = y + WEATHER_SECTION_H

    font_temp_huge = _load_font(True, 72)
    font_temp_unit = _load_font(False, 28)
    font_minmax = _load_font(True, 16)
    font_label = _load_font(True, 14)
    font_wind = _load_font(True, 16)
    font_date_day = _load_font(True, 64)
    font_date_month = _load_font(True, 16)

    # --- LEFT: Temperature (dominant) ---
    temp_x = SIDE_PADDING
    temp_str = f"{int(round(weather.current_temp))}"
    draw.text((temp_x, y + 8), temp_str, fill=BLACK, font=font_temp_huge)
    bbox = draw.textbbox((temp_x, y + 8), temp_str, font=font_temp_huge)
    unit_x = bbox[2] + 4
    draw.text((unit_x, y + 14), "°C", fill=BLACK, font=font_temp_unit)

    # Min/max right of °C, top-aligned
    minmax_x = unit_x + 50
    draw.text((minmax_x, y + 14), f"\u2191 {int(round(weather.temp_max_today))}°", fill=BLACK, font=font_minmax)
    draw.text((minmax_x, y + 34), f"\u2193 {int(round(weather.temp_min_today))}°", fill=BLACK, font=font_minmax)

    # Wind top-right of left area, right-aligned
    divider_x = DISPLAY_WIDTH // 2 + 60
    wind_str = f"{int(round(weather.wind_speed))} km/h {weather.wind_direction}"
    wind_bbox = draw.textbbox((0, 0), wind_str, font=font_wind)
    wind_w = wind_bbox[2] - wind_bbox[0]
    wind_icon_sz = 36
    wind_total = wind_icon_sz + 8 + wind_w
    wind_start_x = divider_x - 16 - wind_total
    draw_icon(draw, "windy", wind_start_x, y + 10, wind_icon_sz, BLACK)
    draw.text((wind_start_x + wind_icon_sz + 8, y + 14), wind_str, fill=BLACK, font=font_wind)

    # Weather icon + label (row 1)
    icon_sz = 36
    icon1_x = SIDE_PADDING + 10
    icon1_y = y + 82
    draw_icon(draw, weather.current_icon, icon1_x, icon1_y, icon_sz, BLACK)
    desc_label = weather.current_desc
    draw.text((icon1_x + icon_sz + 8, icon1_y + 8), desc_label, fill=BLACK, font=font_label)

    # Rain icon + percentage (row 2, below)
    icon2_y = icon1_y + icon_sz + 6
    draw_icon(draw, "rain", icon1_x, icon2_y, icon_sz, BLACK)
    rain_str = f"{int(round(weather.precip_probability))}%"
    draw.text((icon1_x + icon_sz + 8, icon2_y + 8), rain_str, fill=BLACK, font=font_label)

    # --- VERTICAL DIVIDER ---
    draw.line([(divider_x, y + 12), (divider_x, section_bottom - 12)], fill=BLACK, width=2)

    # --- RIGHT: Date ---
    today = date.today()
    right_center_x = divider_x + (DISPLAY_WIDTH - divider_x) // 2

    # Day number (large)
    day_str = str(today.day)
    day_bbox = draw.textbbox((0, 0), day_str, font=font_date_day)
    day_w = day_bbox[2] - day_bbox[0]
    day_h = day_bbox[3] - day_bbox[1]
    day_y = y + (WEATHER_SECTION_H - day_h - 24) // 2
    draw.text((right_center_x - day_w // 2, day_y), day_str, fill=BLACK, font=font_date_day)

    # Month + year
    month_names = ["", "Jänner", "Februar", "März", "April", "Mai", "Juni",
                   "Juli", "August", "September", "Oktober", "November", "Dezember"]
    month_str = f"{month_names[today.month]} {today.year}"
    month_bbox = draw.textbbox((0, 0), month_str, font=font_date_month)
    month_w = month_bbox[2] - month_bbox[0]
    draw.text((right_center_x - month_w // 2, day_y + day_h + 8), month_str, fill=BLACK, font=font_date_month)

    # Bottom border of section
    draw.line([(0, section_bottom - 1), (DISPLAY_WIDTH, section_bottom - 1)], fill=BLACK, width=2)


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
    label_area_h = 40
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

    # Draw connecting lines segment by segment, stopping short of each icon
    icon_sz = 38
    icon_margin = 8  # gap between line end and icon edge

    def _shorten_segment(x1: int, y1: int, x2: int, y2: int, r: int) -> tuple[int, int, int, int] | None:
        """Shorten a line segment so it stops r pixels from each endpoint."""
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 2 * r:
            return None  # too short to draw
        ux, uy = dx / length, dy / length
        return (int(x1 + ux * r), int(y1 + uy * r), int(x2 - ux * r), int(y2 - uy * r))

    past_pts = [(px, py) for i, px, py, is_p in avg_positions if is_p]
    today_pt = next(((px, py) for i, px, py, _ in avg_positions if _is_today(i)), None)
    future_pts = [(px, py) for i, px, py, _ in avg_positions if not _is_past(i) and not _is_today(i)]

    half_icon = icon_sz // 2 + icon_margin

    # Gray segments: past + bridge to today
    gray_line = past_pts[:]
    if today_pt:
        gray_line.append(today_pt)
    for j in range(len(gray_line) - 1):
        seg = _shorten_segment(gray_line[j][0], gray_line[j][1], gray_line[j + 1][0], gray_line[j + 1][1], half_icon)
        if seg:
            draw.line([seg[0], seg[1], seg[2], seg[3]], fill=GRAY, width=2)

    # Black segments: today + future
    black_line = []
    if today_pt:
        black_line.append(today_pt)
    black_line.extend(future_pts)
    for j in range(len(black_line) - 1):
        seg = _shorten_segment(black_line[j][0], black_line[j][1], black_line[j + 1][0], black_line[j + 1][1], half_icon)
        if seg:
            draw.line([seg[0], seg[1], seg[2], seg[3]], fill=BLACK, width=3)

    # --- Draw circles, mini icons, and avg temp below dots ---
    font_dot_temp = _load_font(True, 20)
    for i, p in enumerate(points):
        if p is None:
            continue
        px = day_x(i)
        py = temp_to_y(p[3])
        is_past = _is_past(i)
        is_today_flag = _is_today(i)

        dot_color = GRAY if is_past else BLACK

        # Weather icon centered on data point
        # Today: filled, future: outline only, past: filled gray
        is_future = not is_past and not is_today_flag
        icon_x = px - icon_sz // 2
        icon_y = py - icon_sz // 2
        draw_icon(draw, p[4], icon_x, icon_y, icon_sz, dot_color, outline_only=is_future)

        # Avg temperature below the icon
        avg_str = f"{int(round(p[3]))}°"
        avg_bbox = draw.textbbox((0, 0), avg_str, font=font_dot_temp)
        avg_w = avg_bbox[2] - avg_bbox[0]
        draw.text((px - avg_w // 2, py + icon_sz // 2 + 4), avg_str, fill=dot_color, font=font_dot_temp)

    # --- X-axis labels ---
    font_day = _load_font(True, 20)
    font_minmax_axis = _load_font(False, 11)
    label_y = chart_bottom + 8
    for i, (d, p) in enumerate(zip(week_dates, points)):
        px = day_x(i)
        is_past = _is_past(i)
        lbl_color = GRAY if is_past else BLACK
        wd = WEEKDAYS[d.weekday()]

        # Row 1: weekday name (centred, larger)
        bbox = draw.textbbox((0, 0), wd, font=font_day)
        lw = bbox[2] - bbox[0]
        draw.text((px - lw // 2, label_y), wd, fill=lbl_color, font=font_day)

        if p is None:
            continue

        d_val, t_min, t_max, t_avg, icon = p

        # Row 2: min° / max°
        minmax_str = f"{int(round(t_min))}° / {int(round(t_max))}°"
        mm_bbox = draw.textbbox((0, 0), minmax_str, font=font_minmax_axis)
        mm_w = mm_bbox[2] - mm_bbox[0]
        row2_y = label_y + 17
        draw.text((px - mm_w // 2, row2_y), minmax_str, fill=lbl_color, font=font_minmax_axis)


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
