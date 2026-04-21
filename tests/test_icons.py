from PIL import Image, ImageDraw
from src.icons import draw_icon, ICON_NAMES


def test_all_icon_names_exist():
    expected = [
        "clear", "partly_cloudy", "mostly_cloudy", "overcast", "fog",
        "drizzle", "rain", "heavy_rain", "freezing_rain", "rain_shower",
        "light_snow", "snow", "heavy_snow", "sleet",
        "thunderstorm", "thunderstorm_rain", "thunderstorm_hail", "windy",
    ]
    for name in expected:
        assert name in ICON_NAMES, f"Missing icon: {name}"


def test_draw_icon_does_not_crash():
    img = Image.new("L", (100, 100), 255)
    draw = ImageDraw.Draw(img)
    for name in ICON_NAMES:
        draw_icon(draw, name, x=10, y=10, size=80, color=0)


def test_draw_icon_small_size():
    img = Image.new("L", (50, 50), 255)
    draw = ImageDraw.Draw(img)
    for name in ICON_NAMES:
        draw_icon(draw, name, x=5, y=5, size=24, color=0)


def test_draw_icon_produces_pixels():
    img = Image.new("L", (100, 100), 255)
    draw = ImageDraw.Draw(img)
    draw_icon(draw, "clear", x=10, y=10, size=80, color=0)
    pixels = list(img.getdata())
    assert any(p < 255 for p in pixels), "Icon drew nothing"


def test_draw_icon_unknown_falls_back():
    img = Image.new("L", (100, 100), 255)
    draw = ImageDraw.Draw(img)
    draw_icon(draw, "unknown_weather", x=10, y=10, size=80, color=0)
