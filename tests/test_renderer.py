from datetime import date
from unittest.mock import patch
from PIL import Image
from src.renderer import (
    render_display, DISPLAY_WIDTH, DISPLAY_HEIGHT,
    STATUS_BAR_H, WEATHER_SECTION_H, SIDE_PADDING, CHART_MARGIN_LEFT, CHART_MARGIN_RIGHT,
)
from src.weather import WeatherData, DayForecast


def _sample_weather() -> WeatherData:
    today = date(2026, 4, 17)
    week = [
        DayForecast(date=date(2026, 4, 14), temp_min=5, temp_max=18, temp_avg=12, icon="overcast"),
        DayForecast(date=date(2026, 4, 15), temp_min=7, temp_max=20, temp_avg=14, icon="rain"),
        DayForecast(date=date(2026, 4, 16), temp_min=8, temp_max=22, temp_avg=16, icon="partly_cloudy"),
        DayForecast(date=date(2026, 4, 17), temp_min=10, temp_max=25, temp_avg=19, icon="clear"),
        DayForecast(date=date(2026, 4, 18), temp_min=9, temp_max=23, temp_avg=17, icon="mostly_cloudy"),
        DayForecast(date=date(2026, 4, 19), temp_min=8, temp_max=24, temp_avg=18, icon="overcast"),
        DayForecast(date=date(2026, 4, 20), temp_min=7, temp_max=21, temp_avg=16, icon="rain"),
    ]
    return WeatherData(
        current_temp=23, current_icon="clear", current_desc="Sonnig",
        wind_speed=12, wind_direction="NW", precip_probability=10,
        temp_min_today=10, temp_max_today=25,
        week=week, timestamp="2026-04-17T10:00:00",
    )


def test_render_display_returns_correct_size():
    img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien")
    assert img.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)


def test_render_display_is_grayscale():
    img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien")
    assert img.mode == "L"


def test_render_display_has_content():
    img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien")
    pixels = list(img.getdata())
    white_count = sum(1 for p in pixels if p > 250)
    assert white_count < len(pixels) * 0.95


def test_render_display_preview_saves_png(tmp_path):
    img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien")
    path = tmp_path / "preview.png"
    img.save(str(path))
    assert path.exists()
    loaded = Image.open(str(path))
    assert loaded.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)


def test_render_display_no_city():
    img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450)
    assert img.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)


def test_render_display_charging_differs_from_not_charging():
    img_off = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien", charging=False)
    img_on = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien", charging=True)
    assert list(img_off.getdata()) != list(img_on.getdata())


def test_render_display_charging_true_keeps_size_and_mode():
    img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien", charging=True)
    assert img.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)
    assert img.mode == "L"


def test_render_display_charging_defaults_to_false():
    # Callers that don't pass charging= (existing tests above, __main__ preview) must
    # keep working unchanged.
    img_default = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien")
    img_explicit_false = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien", charging=False)
    assert list(img_default.getdata()) == list(img_explicit_false.getdata())


def test_render_display_charging_ignores_battery_level_for_fill():
    # Cutout style fills the whole battery body solid black regardless of the
    # reported level — the level reading is unreliable while charging (charger
    # holds the cell at ~constant voltage), so a 5% reading must look identical
    # to a 95% reading while charging: fully filled, not a thin sliver.
    img_low_charging = render_display(_sample_weather(), battery_pct=5, off_grid_days=0, city="Wien", charging=True)
    img_low_not_charging = render_display(_sample_weather(), battery_pct=5, off_grid_days=0, city="Wien", charging=False)
    black_charging = sum(1 for p in img_low_charging.getdata() if p < 10)
    black_not_charging = sum(1 for p in img_low_not_charging.getdata() if p < 10)
    # At 5% the non-charging fill bar is nearly empty; charging fills the whole
    # body, so it must contain noticeably more black pixels.
    assert black_charging > black_not_charging + 50


def test_render_display_highlights_today_column():
    # 2026-04-17 is the "current_temp" day in _sample_weather()'s week, so
    # pinning date.today() to it puts "today" inside the rendered 7-day window
    # and the highlight bar should draw. Patching src.renderer.date also shifts
    # _draw_weather_section's date line, which is expected and harmless here.
    with patch("src.renderer.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 17)
        img_today = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien")
    # Real system date isn't inside the sample week, so no column is highlighted.
    img_baseline = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien")

    black_today = sum(1 for p in img_today.getdata() if p < 10)
    black_baseline = sum(1 for p in img_baseline.getdata() if p < 10)
    # The highlight bar alone adds roughly col_width (~94px) × (DISPLAY_HEIGHT -
    # chart_top) (~251px) ≈ 23,000 solid-black pixels — far more than the
    # handful of chart lines/icons it replaces within that column.
    assert black_today > black_baseline + 10000


def _chart_column_x_range(day_index: int) -> tuple[int, int]:
    chart_left = SIDE_PADDING + CHART_MARGIN_LEFT
    chart_right = DISPLAY_WIDTH - SIDE_PADDING - CHART_MARGIN_RIGHT
    col_w = (chart_right - chart_left) / 7
    col_left = int(chart_left + day_index * col_w)
    col_right = int(chart_left + (day_index + 1) * col_w)
    return col_left, col_right


def _rotated_180_rect(x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int]:
    # render_display() returns img.rotate(180) - map a rect computed in the
    # pre-rotation drawing coordinates to where it ends up in the final image.
    return (
        DISPLAY_WIDTH - x1, DISPLAY_HEIGHT - y1,
        DISPLAY_WIDTH - x0, DISPLAY_HEIGHT - y0,
    )


def test_render_display_weekday_label_sits_above_plot():
    # 2026-04-17 is a Friday in _sample_weather()'s week; day_index 0
    # (2026-04-14, Monday) is a "past" day, never the highlighted "today"
    # column, so its label always renders in plain black/gray text -
    # simplest column to probe for the weekday label's y-position.
    with patch("src.renderer.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 17)
        img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien")

    y_start = STATUS_BAR_H + WEATHER_SECTION_H
    col_left, col_right = _chart_column_x_range(0)

    # Directly under y_start is reserved chart top-padding in the old layout
    # (nothing drawn there) - the weekday label now lives in this band.
    header_band = img.crop(_rotated_180_rect(col_left, y_start, col_right, y_start + 12))
    header_pixels = list(header_band.getdata())
    assert any(p < 100 for p in header_pixels), (
        "expected the weekday label to render in a header band just below y_start"
    )


def test_render_display_only_todays_minmax_shown_below_chart():
    with patch("src.renderer.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 17)
        img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450, city="Wien")

    # day_index 0 (2026-04-14, Monday) is never "today" - its column must have
    # no temperature text left in the bottom label area. Start a few pixels
    # below DISPLAY_HEIGHT - 40 to skip over the chart's x-axis line itself,
    # which legitimately spans every column.
    col_left, col_right = _chart_column_x_range(0)
    footer_band = img.crop(_rotated_180_rect(col_left, DISPLAY_HEIGHT - 32, col_right, DISPLAY_HEIGHT))
    footer_pixels = list(footer_band.getdata())
    assert all(p > 100 for p in footer_pixels), (
        "non-today columns must not show min/max text below the chart anymore"
    )
