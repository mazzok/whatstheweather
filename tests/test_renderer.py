from datetime import date
from PIL import Image
from src.renderer import render_display, DISPLAY_WIDTH, DISPLAY_HEIGHT
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
    img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450)
    assert img.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)


def test_render_display_is_grayscale():
    img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450)
    assert img.mode == "L"


def test_render_display_has_content():
    img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450)
    pixels = list(img.getdata())
    white_count = sum(1 for p in pixels if p > 250)
    assert white_count < len(pixels) * 0.95


def test_render_display_preview_saves_png(tmp_path):
    img = render_display(_sample_weather(), battery_pct=78, off_grid_days=2450)
    path = tmp_path / "preview.png"
    img.save(str(path))
    assert path.exists()
    loaded = Image.open(str(path))
    assert loaded.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)
