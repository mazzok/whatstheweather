import math
from PIL import ImageDraw

ICON_NAMES = [
    "clear", "partly_cloudy", "mostly_cloudy", "overcast", "fog",
    "drizzle", "rain", "heavy_rain", "freezing_rain", "rain_shower",
    "light_snow", "snow", "heavy_snow", "sleet",
    "thunderstorm", "thunderstorm_rain", "thunderstorm_hail", "windy",
]


def draw_icon(draw: ImageDraw.Draw, name: str, x: int, y: int, size: int, color: int, outline_only: bool = False) -> None:
    fn = _ICONS.get(name, _draw_overcast)
    fn(draw, x, y, size, color, outline_only=outline_only)


def _s(size: int, val: float) -> float:
    """Scale a value from 80px reference to target size."""
    return val * size / 80


def _cloud(draw, x, y, size, color, cy_offset=0, outline_only=False):
    """Draw a standard cloud shape."""
    s = lambda v: _s(size, v)
    cx, cy = x + s(40), y + s(38 + cy_offset)
    r1 = s(22)
    r2 = s(14)
    w = max(1, int(s(2.5)))
    if outline_only:
        draw.ellipse([cx - r1, cy - r2, cx + r1, cy + r2], outline=color, width=w)
        draw.ellipse([cx - r1 + s(5), cy - r2 - s(10), cx + s(5), cy - s(2)], outline=color, width=w)
        draw.ellipse([cx - s(5), cy - r2 - s(6), cx + r1 - s(5), cy], outline=color, width=w)
    else:
        draw.ellipse([cx - r1, cy - r2, cx + r1, cy + r2], fill=color)
        draw.ellipse([cx - r1 + s(5), cy - r2 - s(10), cx + s(5), cy - s(2)], fill=color)
        draw.ellipse([cx - s(5), cy - r2 - s(6), cx + r1 - s(5), cy], fill=color)


def _sun_rays(draw, cx, cy, r_inner, r_outer, color, width):
    """Draw sun rays."""
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1 = cx + r_inner * math.cos(rad)
        y1 = cy + r_inner * math.sin(rad)
        x2 = cx + r_outer * math.cos(rad)
        y2 = cy + r_outer * math.sin(rad)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=width)


def _snowflake(draw, cx, cy, r, color, width):
    """Draw a snowflake asterisk."""
    for angle in [0, 60, 120]:
        rad = math.radians(angle)
        dx = r * math.cos(rad)
        dy = r * math.sin(rad)
        draw.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], fill=color, width=width)


def _draw_clear(draw, x, y, size, color, outline_only=False):
    s = lambda v: _s(size, v)
    cx, cy = x + s(40), y + s(40)
    r = s(12)
    w = max(1, int(s(3)))
    if outline_only:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=w)
    else:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    _sun_rays(draw, cx, cy, r + s(4), r + s(16), color, w)


def _draw_partly_cloudy(draw, x, y, size, color, outline_only=False):
    s = lambda v: _s(size, v)
    sx, sy = x + s(28), y + s(26)
    r = s(10)
    w = max(1, int(s(2.5)))
    if outline_only:
        draw.ellipse([sx - r, sy - r, sx + r, sy + r], outline=color, width=w)
    else:
        draw.ellipse([sx - r, sy - r, sx + r, sy + r], outline=color, width=w)
    _sun_rays(draw, sx, sy, r + s(3), r + s(10), color, w)
    _cloud(draw, x + s(8), y + s(8), int(size * 0.75), color, cy_offset=4, outline_only=outline_only)


def _draw_mostly_cloudy(draw, x, y, size, color, outline_only=False):
    s = lambda v: _s(size, v)
    w = max(1, int(s(2.5)))
    sx, sy = x + s(22), y + s(20)
    r = s(6)
    _sun_rays(draw, sx, sy, r + s(2), r + s(8), color, w)
    _cloud(draw, x, y + s(4), size, color, outline_only=outline_only)


def _draw_overcast(draw, x, y, size, color, outline_only=False):
    _cloud(draw, x, y, size, color, outline_only=outline_only)


def _draw_fog(draw, x, y, size, color, outline_only=False):
    s = lambda v: _s(size, v)
    w = max(1, int(s(3.5)))
    for i, yoff in enumerate([26, 38, 50, 62]):
        indent = s(6) if i % 2 else 0
        draw.line([(x + indent, y + s(yoff)), (x + size - indent, y + s(yoff))],
                  fill=color, width=w)


def _rain_lines(draw, x, y, size, color, count, width_scale=2.5):
    s = lambda v: _s(size, v)
    w = max(1, int(s(width_scale)))
    spacing = s(50) / max(count, 1)
    start_x = x + s(15)
    for i in range(count):
        lx = start_x + i * spacing
        draw.line([(lx, y + s(50)), (lx - s(3), y + s(64))], fill=color, width=w)


def _draw_drizzle(draw, x, y, size, color, outline_only=False):
    _cloud(draw, x, y - _s(size, 6), size, color, cy_offset=-4, outline_only=outline_only)
    _rain_lines(draw, x, y, size, color, 2)


def _draw_rain(draw, x, y, size, color, outline_only=False):
    _cloud(draw, x, y - _s(size, 6), size, color, cy_offset=-4, outline_only=outline_only)
    _rain_lines(draw, x, y, size, color, 3)


def _draw_heavy_rain(draw, x, y, size, color, outline_only=False):
    _cloud(draw, x, y - _s(size, 8), size, color, cy_offset=-6, outline_only=outline_only)
    _rain_lines(draw, x, y, size, color, 4, width_scale=3)


def _draw_freezing_rain(draw, x, y, size, color, outline_only=False):
    _cloud(draw, x, y - _s(size, 6), size, color, cy_offset=-4, outline_only=outline_only)
    s = lambda v: _s(size, v)
    w = max(1, int(s(2.5)))
    draw.line([(x + s(22), y + s(50)), (x + s(19), y + s(62))], fill=color, width=w)
    draw.line([(x + s(36), y + s(50)), (x + s(33), y + s(62))], fill=color, width=w)
    _snowflake(draw, x + s(54), y + s(58), s(7), color, w)


def _draw_rain_shower(draw, x, y, size, color, outline_only=False):
    s = lambda v: _s(size, v)
    cx, cy = x + s(40), y + s(34)
    r1, r2 = s(24), s(12)
    w = max(1, int(s(2.5)))
    if outline_only:
        draw.ellipse([cx - r1, cy - r2, cx + r1, cy + r2], outline=color, width=w)
        draw.ellipse([cx - s(12), cy - r2 - s(14), cx + s(8), cy - s(4)], outline=color, width=w)
        draw.ellipse([cx + s(2), cy - r2 - s(8), cx + r1 - s(2), cy], outline=color, width=w)
        draw.ellipse([cx - r1 + s(2), cy - r2 - s(6), cx - s(8), cy], outline=color, width=w)
    else:
        draw.ellipse([cx - r1, cy - r2, cx + r1, cy + r2], fill=color)
        draw.ellipse([cx - s(12), cy - r2 - s(14), cx + s(8), cy - s(4)], fill=color)
        draw.ellipse([cx + s(2), cy - r2 - s(8), cx + r1 - s(2), cy], fill=color)
        draw.ellipse([cx - r1 + s(2), cy - r2 - s(6), cx - s(8), cy], fill=color)
    _rain_lines(draw, x, y, size, color, 3)


def _draw_light_snow(draw, x, y, size, color, outline_only=False):
    s = lambda v: _s(size, v)
    _cloud(draw, x, y - s(6), size, color, cy_offset=-4, outline_only=outline_only)
    w = max(1, int(s(2.5)))
    _snowflake(draw, x + s(28), y + s(58), s(5), color, w)
    _snowflake(draw, x + s(50), y + s(58), s(5), color, w)


def _draw_snow(draw, x, y, size, color, outline_only=False):
    s = lambda v: _s(size, v)
    _cloud(draw, x, y - s(8), size, color, cy_offset=-6, outline_only=outline_only)
    w = max(1, int(s(2.5)))
    _snowflake(draw, x + s(20), y + s(56), s(5), color, w)
    _snowflake(draw, x + s(40), y + s(58), s(5), color, w)
    _snowflake(draw, x + s(58), y + s(56), s(5), color, w)


def _draw_heavy_snow(draw, x, y, size, color, outline_only=False):
    s = lambda v: _s(size, v)
    _cloud(draw, x, y - s(10), size, color, cy_offset=-8, outline_only=outline_only)
    w = max(1, int(s(3)))
    _snowflake(draw, x + s(14), y + s(54), s(5), color, w)
    _snowflake(draw, x + s(30), y + s(56), s(5), color, w)
    _snowflake(draw, x + s(46), y + s(54), s(5), color, w)
    _snowflake(draw, x + s(62), y + s(56), s(5), color, w)


def _draw_sleet(draw, x, y, size, color, outline_only=False):
    s = lambda v: _s(size, v)
    _cloud(draw, x, y - s(6), size, color, cy_offset=-4, outline_only=outline_only)
    w = max(1, int(s(2.5)))
    draw.line([(x + s(24), y + s(50)), (x + s(21), y + s(62))], fill=color, width=w)
    draw.line([(x + s(38), y + s(50)), (x + s(35), y + s(62))], fill=color, width=w)
    _snowflake(draw, x + s(54), y + s(58), s(5), color, w)


def _draw_thunderstorm(draw, x, y, size, color, outline_only=False):
    s = lambda v: _s(size, v)
    _cloud(draw, x, y - s(8), size, color, cy_offset=-6, outline_only=outline_only)
    w = max(1, int(s(2)))
    points = [
        (x + s(42), y + s(42)),
        (x + s(34), y + s(56)),
        (x + s(42), y + s(56)),
        (x + s(36), y + s(70)),
    ]
    draw.line(points, fill=255, width=w + 2)
    draw.line(points, fill=color, width=w)


def _draw_thunderstorm_rain(draw, x, y, size, color, outline_only=False):
    _draw_thunderstorm(draw, x, y, size, color, outline_only=outline_only)
    s = lambda v: _s(size, v)
    w = max(1, int(s(2.5)))
    draw.line([(x + s(18), y + s(48)), (x + s(15), y + s(60))], fill=color, width=w)
    draw.line([(x + s(58), y + s(48)), (x + s(55), y + s(60))], fill=color, width=w)


def _draw_thunderstorm_hail(draw, x, y, size, color, outline_only=False):
    _draw_thunderstorm(draw, x, y, size, color, outline_only=outline_only)
    s = lambda v: _s(size, v)
    r = s(3.5)
    w = max(1, int(s(2)))
    draw.ellipse([x + s(18) - r, y + s(54) - r, x + s(18) + r, y + s(54) + r],
                 outline=color, width=w)
    draw.ellipse([x + s(58) - r, y + s(52) - r, x + s(58) + r, y + s(52) + r],
                 outline=color, width=w)


def _draw_windy(draw, x, y, size, color, outline_only=False):
    s = lambda v: _s(size, v)
    w = max(1, int(s(3)))
    pts1 = [(x + s(10), y + s(30))]
    for t in range(20):
        px = x + s(10 + t * 2.2)
        py = y + s(30) - s(4) * math.sin(t * 0.3)
        pts1.append((px, py))
    draw.line(pts1, fill=color, width=w)
    pts2 = [(x + s(10), y + s(44))]
    for t in range(25):
        px = x + s(10 + t * 2.4)
        py = y + s(44) - s(3) * math.sin(t * 0.25)
        pts2.append((px, py))
    draw.line(pts2, fill=color, width=w)
    pts3 = [(x + s(10), y + s(58))]
    for t in range(18):
        px = x + s(10 + t * 2)
        py = y + s(58) - s(3) * math.sin(t * 0.35)
        pts3.append((px, py))
    draw.line(pts3, fill=color, width=w)


_ICONS = {
    "clear": _draw_clear,
    "partly_cloudy": _draw_partly_cloudy,
    "mostly_cloudy": _draw_mostly_cloudy,
    "overcast": _draw_overcast,
    "fog": _draw_fog,
    "drizzle": _draw_drizzle,
    "rain": _draw_rain,
    "heavy_rain": _draw_heavy_rain,
    "freezing_rain": _draw_freezing_rain,
    "rain_shower": _draw_rain_shower,
    "light_snow": _draw_light_snow,
    "snow": _draw_snow,
    "heavy_snow": _draw_heavy_snow,
    "sleet": _draw_sleet,
    "thunderstorm": _draw_thunderstorm,
    "thunderstorm_rain": _draw_thunderstorm_rain,
    "thunderstorm_hail": _draw_thunderstorm_hail,
    "windy": _draw_windy,
}
