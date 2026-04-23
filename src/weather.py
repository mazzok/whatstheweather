# src/weather.py
import json
import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://dataset.api.hub.geosphere.at"
TIMEOUT = 30
CACHE_PATH = Path.home() / ".weather_cache.json"

SY_MAP = {
    1: "clear", 2: "clear",
    3: "partly_cloudy", 4: "mostly_cloudy",
    5: "overcast",
    6: "fog", 7: "fog",
    8: "drizzle", 9: "rain", 10: "heavy_rain",
    11: "sleet", 12: "sleet", 13: "sleet",
    14: "light_snow", 15: "snow", 16: "heavy_snow",
    17: "rain", 18: "rain", 19: "rain_shower",
    20: "sleet", 21: "sleet", 22: "sleet",
    23: "light_snow", 24: "snow", 25: "heavy_snow",
    26: "thunderstorm", 27: "thunderstorm_rain",
    28: "thunderstorm_rain", 29: "thunderstorm_hail",
    30: "thunderstorm", 31: "thunderstorm_rain",
    32: "thunderstorm_hail",
}

WMO_CODE_MAP = {
    0: "clear", 1: "clear", 2: "partly_cloudy", 3: "overcast",
    45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "drizzle",
    56: "freezing_rain", 57: "freezing_rain",
    61: "rain", 63: "rain", 65: "heavy_rain",
    66: "freezing_rain", 67: "freezing_rain",
    71: "light_snow", 73: "snow", 75: "heavy_snow",
    77: "snow",
    80: "rain_shower", 81: "rain_shower", 82: "heavy_rain",
    85: "light_snow", 86: "heavy_snow",
    95: "thunderstorm", 96: "thunderstorm_hail", 99: "thunderstorm_hail",
}

COMPASS = ["N", "NO", "O", "SO", "S", "SW", "W", "NW"]

WEATHER_DESCRIPTIONS = {
    "clear": "Sonnig", "partly_cloudy": "Teils bewölkt",
    "mostly_cloudy": "Überwiegend bewölkt", "overcast": "Bewölkt",
    "fog": "Nebel", "drizzle": "Nieselregen", "rain": "Regen",
    "heavy_rain": "Starkregen", "freezing_rain": "Gefrierender Regen",
    "rain_shower": "Regenschauer", "light_snow": "Leichter Schnee",
    "snow": "Schnee", "heavy_snow": "Starker Schnee", "sleet": "Schneeregen",
    "thunderstorm": "Gewitter", "thunderstorm_rain": "Gewitter mit Regen",
    "thunderstorm_hail": "Gewitter mit Hagel", "windy": "Windig",
}

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class DayForecast:
    date: date
    temp_min: float
    temp_max: float
    temp_avg: float
    icon: str  # one of the 18 icon names


@dataclass
class WeatherData:
    current_temp: float
    current_icon: str
    current_desc: str
    wind_speed: float        # km/h
    wind_direction: str      # compass direction
    precip_probability: float  # 0-100%
    temp_min_today: float
    temp_max_today: float
    week: list[DayForecast] = field(default_factory=list)  # Mo-So
    timestamp: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def wind_speed_and_direction(u: float, v: float) -> tuple[float, str]:
    """Convert u/v wind components (m/s) to speed (km/h) and compass direction.

    Meteorological convention: the direction indicates where the wind comes FROM.
    A positive u component means wind blows eastward → comes FROM the west.
    A positive v component means wind blows northward → comes FROM the south.
    """
    speed_ms = math.sqrt(u * u + v * v)
    speed_kmh = speed_ms * 3.6

    # Wind direction: the direction FROM which the wind blows.
    # math.atan2(-u, -v) gives the meteorological wind direction in radians,
    # measured clockwise from north.
    angle_deg = math.degrees(math.atan2(-u, -v)) % 360
    # Map to 8 compass sectors (each 45°), offset by 22.5° to centre each sector
    index = int((angle_deg + 22.5) / 45) % 8
    direction = COMPASS[index]

    return speed_kmh, direction


def map_sy_code(code: float) -> str:
    """Map a GeoSphere sy (weather symbol) code to an icon name string."""
    try:
        if math.isnan(code):
            return "overcast"
        return SY_MAP.get(int(code), "overcast")
    except (ValueError, TypeError):
        return "overcast"


def aggregate_daily_forecast(
    timestamps: list[str],
    t2m: list[float],
    sy: list[float],
) -> list[DayForecast]:
    """Aggregate hourly NWP data into per-day DayForecast entries.

    Timestamps must be ISO-8601 strings. Returns days sorted by date.
    """
    if not timestamps:
        return []

    daily: dict[date, dict] = {}

    for ts_str, temp, sy_code in zip(timestamps, t2m, sy):
        dt = datetime.fromisoformat(ts_str)
        d = dt.date()
        if d not in daily:
            daily[d] = {"temps": [], "sy_codes": []}
        daily[d]["temps"].append(temp)
        daily[d]["sy_codes"].append(sy_code)

    result: list[DayForecast] = []
    for d in sorted(daily.keys()):
        entry = daily[d]
        temps = entry["temps"]
        sy_codes = entry["sy_codes"]

        temp_min = min(temps)
        temp_max = max(temps)
        temp_avg = sum(temps) / len(temps)

        # Dominant icon: most common mapped icon
        icons = [map_sy_code(c) for c in sy_codes]
        counter = Counter(icons)
        icon = counter.most_common(1)[0][0]

        result.append(DayForecast(
            date=d,
            temp_min=temp_min,
            temp_max=temp_max,
            temp_avg=temp_avg,
            icon=icon,
        ))

    return result


def _daterange(start: date, end: date) -> list[date]:
    """Return a list of dates from start to end (inclusive)."""
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def find_nearest_station(lat: float, lon: float, stations: list[dict]) -> dict | None:
    """Return the active station closest to (lat, lon), or None if none available."""
    active = [s for s in stations if s.get("is_active", False)]
    if not active:
        return None

    def _distance(s: dict) -> float:
        dlat = s["lat"] - lat
        dlon = s["lon"] - lon
        return dlat * dlat + dlon * dlon

    return min(active, key=_distance)


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def fetch_station_metadata(dataset: str = "tawes-v1-10min") -> list[dict]:
    """Fetch station list from a GeoSphere metadata endpoint.

    dataset can be 'tawes-v1-10min' (current) or 'klima-v2-1d' (historical).
    """
    if dataset == "klima-v2-1d":
        url = f"{BASE_URL}/v1/station/historical/{dataset}/metadata"
    else:
        url = f"{BASE_URL}/v1/station/current/{dataset}/metadata"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.error("Station metadata (%s) HTTP %d", dataset, resp.status_code)
            return []
        data = resp.json()
        return data.get("stations", [])
    except Exception as exc:
        logger.error("fetch_station_metadata (%s) error: %s", dataset, exc)
        return []


def fetch_historical(station_id: str, start: date, end: date) -> list[DayForecast]:
    """Fetch historical daily data from klima-v2-1d for a station and date range.

    Returns a list of DayForecast entries for each day in the range.
    """
    if start > end:
        return []
    url = (
        f"{BASE_URL}/v1/station/historical/klima-v2-1d"
        f"?parameters=tl_mittel,tlmax,tlmin,rr,bewm_mittel,so_h,nebel,gew"
        f"&start={start.isoformat()}T00:00:00"
        f"&end={end.isoformat()}T00:00:00"
        f"&station_ids={station_id}"
    )
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.error("Historical HTTP %d", resp.status_code)
            return []
        data = resp.json()
        timestamps = data.get("timestamps", [])
        props = data["features"][0]["properties"]["parameters"]
        tl_mittel = props["tl_mittel"]["data"]
        tlmax = props["tlmax"]["data"]
        tlmin = props["tlmin"]["data"]
        rr = props.get("rr", {}).get("data", [0.0] * len(timestamps))
        bewm = props.get("bewm_mittel", {}).get("data", [50.0] * len(timestamps))
        so_h = props.get("so_h", {}).get("data", [0.0] * len(timestamps))
        nebel = props.get("nebel", {}).get("data", [0] * len(timestamps))
        gew = props.get("gew", {}).get("data", [0] * len(timestamps))

        result: list[DayForecast] = []
        for i, ts_str in enumerate(timestamps):
            d = datetime.fromisoformat(ts_str).date()
            icon = _derive_icon_from_historical(
                rr[i] if i < len(rr) else 0.0,
                bewm[i] if i < len(bewm) else 50.0,
                so_h[i] if i < len(so_h) else 0.0,
                nebel[i] if i < len(nebel) else 0,
                gew[i] if i < len(gew) else 0,
            )
            t_avg = tl_mittel[i] if i < len(tl_mittel) and tl_mittel[i] is not None else 0.0
            t_max = tlmax[i] if i < len(tlmax) and tlmax[i] is not None else t_avg
            t_min = tlmin[i] if i < len(tlmin) and tlmin[i] is not None else t_avg
            result.append(DayForecast(date=d, temp_min=t_min, temp_max=t_max, temp_avg=t_avg, icon=icon))
        return result
    except Exception as exc:
        logger.error("fetch_historical error: %s", exc)
        return []


def _derive_icon_from_historical(rr: float, bewm: float, so_h: float, nebel: float, gew: float) -> str:
    """Derive a weather icon name from historical daily measurements."""
    if gew and gew > 0:
        if rr and rr > 1.0:
            return "thunderstorm_rain"
        return "thunderstorm"
    if nebel and nebel > 0:
        return "fog"
    if rr is not None and rr > 10.0:
        return "heavy_rain"
    if rr is not None and rr > 2.0:
        return "rain"
    if rr is not None and rr > 0.5:
        return "drizzle"
    if bewm is not None:
        if bewm > 80:
            return "overcast"
        if bewm > 60:
            return "mostly_cloudy"
        if bewm > 30:
            return "partly_cloudy"
    return "clear"


def fetch_openmeteo_daily(lat: float, lon: float) -> list[DayForecast]:
    """Fetch 7-day daily forecast from Open-Meteo as gap-filler."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,weather_code"
        f"&timezone=Europe/Vienna"
    )
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.error("Open-Meteo HTTP %d", resp.status_code)
            return []
        data = resp.json()
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        t_max = daily.get("temperature_2m_max", [])
        t_min = daily.get("temperature_2m_min", [])
        t_mean = daily.get("temperature_2m_mean", [])
        codes = daily.get("weather_code", [])

        result: list[DayForecast] = []
        for i, ds in enumerate(dates):
            d = date.fromisoformat(ds)
            code = codes[i] if i < len(codes) else 0
            icon = WMO_CODE_MAP.get(code, "overcast")
            avg = t_mean[i] if i < len(t_mean) and t_mean[i] is not None else 0.0
            mx = t_max[i] if i < len(t_max) and t_max[i] is not None else avg
            mn = t_min[i] if i < len(t_min) and t_min[i] is not None else avg
            result.append(DayForecast(date=d, temp_min=mn, temp_max=mx, temp_avg=avg, icon=icon))
        return result
    except Exception as exc:
        logger.error("fetch_openmeteo_daily error: %s", exc)
        return []


def fetch_forecast(lat: float, lon: float) -> dict | None:
    """Fetch NWP forecast for (lat, lon). Returns raw JSON dict or None."""
    url = (
        f"{BASE_URL}/v1/timeseries/forecast/nwp-v1-1h-2500m"
        f"?parameters=t2m,sy,u10m,v10m,rr_acc&lat_lon={lat},{lon}"
    )
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.error("Forecast HTTP %d", resp.status_code)
            return None
        return resp.json()
    except Exception as exc:
        logger.error("fetch_forecast error: %s", exc)
        return None


def fetch_current_weather(station_id: str) -> dict | None:
    """Fetch current TAWES observation for a station. Returns flat dict of latest values or None."""
    url = (
        f"{BASE_URL}/v1/station/current/tawes-v1-10min"
        f"?parameters=TL,RF,DD,FF,RR&station_ids={station_id}"
    )
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.error("TAWES HTTP %d for station %s", resp.status_code, station_id)
            return None
        data = resp.json()
        params = data["features"][0]["properties"]["parameters"]
        return {
            "TL": params["TL"]["data"][-1],
            "RF": params["RF"]["data"][-1],
            "DD": params["DD"]["data"][-1],
            "FF": params["FF"]["data"][-1],
            "RR": params["RR"]["data"][-1],
        }
    except Exception as exc:
        logger.error("fetch_current_weather error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

def _save_cache(weather: WeatherData) -> None:
    """Persist WeatherData to JSON cache file."""
    try:
        payload = {
            "current_temp": weather.current_temp,
            "current_icon": weather.current_icon,
            "current_desc": weather.current_desc,
            "wind_speed": weather.wind_speed,
            "wind_direction": weather.wind_direction,
            "precip_probability": weather.precip_probability,
            "temp_min_today": weather.temp_min_today,
            "temp_max_today": weather.temp_max_today,
            "timestamp": weather.timestamp,
            "error": weather.error,
            "week": [
                {
                    "date": d.date.isoformat(),
                    "temp_min": d.temp_min,
                    "temp_max": d.temp_max,
                    "temp_avg": d.temp_avg,
                    "icon": d.icon,
                }
                for d in weather.week
            ],
        }
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception as exc:
        logger.warning("Could not save weather cache: %s", exc)


def _load_cache() -> WeatherData | None:
    """Load WeatherData from JSON cache file. Returns None if unavailable or corrupt."""
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        week = [
            DayForecast(
                date=date.fromisoformat(d["date"]),
                temp_min=d["temp_min"],
                temp_max=d["temp_max"],
                temp_avg=d["temp_avg"],
                icon=d["icon"],
            )
            for d in payload.get("week", [])
        ]
        return WeatherData(
            current_temp=payload["current_temp"],
            current_icon=payload["current_icon"],
            current_desc=payload["current_desc"],
            wind_speed=payload["wind_speed"],
            wind_direction=payload["wind_direction"],
            precip_probability=payload["precip_probability"],
            temp_min_today=payload["temp_min_today"],
            temp_max_today=payload["temp_max_today"],
            week=week,
            timestamp=payload.get("timestamp", ""),
            error=payload.get("error", ""),
        )
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.warning("Could not load weather cache: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Wind direction from degrees (used when station reports DD in degrees)
# ---------------------------------------------------------------------------

def _deg_to_compass(degrees: float) -> str:
    """Convert a wind-direction in meteorological degrees to a compass label."""
    index = int((degrees + 22.5) / 45) % 8
    return COMPASS[index]


# ---------------------------------------------------------------------------
# Main assembly function
# ---------------------------------------------------------------------------

def get_weather(lat: float, lon: float) -> WeatherData:
    """Assemble current + forecast weather data for (lat, lon).

    Strategy:
    1. Fetch TAWES station list and find nearest active station.
    2. Fetch current observation from that station.
    3. Fetch NWP forecast for the coordinates.
    4. Aggregate into WeatherData, save to cache, return.

    If any step fails gracefully degrades: uses forecast data for current if
    TAWES unavailable; returns cached data if forecast also fails; returns
    WeatherData with error set if everything fails.
    """
    forecast_data = fetch_forecast(lat, lon)

    # Try to get current observation from TAWES
    current_obs: dict | None = None
    stations = fetch_station_metadata()
    nearest = find_nearest_station(lat, lon, stations)
    if nearest:
        current_obs = fetch_current_weather(nearest["id"])

    # Extract forecast arrays
    if forecast_data:
        timestamps = forecast_data.get("timestamps", [])
        props = forecast_data["features"][0]["properties"]["parameters"]
        t2m_data = props["t2m"]["data"]
        sy_data = props["sy"]["data"]
        u10m_data = props["u10m"]["data"]
        v10m_data = props["v10m"]["data"]
        rr_acc_data = props.get("rr_acc", {}).get("data", [0.0] * len(timestamps))

        day_forecasts = aggregate_daily_forecast(timestamps, t2m_data, sy_data)

        # Fill in past days from historical data
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        forecast_dates = {d.date for d in day_forecasts}
        past_start = monday
        past_end = today - timedelta(days=1)

        if past_start <= past_end:
            missing_past = [d for d in _daterange(past_start, past_end) if d not in forecast_dates]
            if missing_past:
                # Historical stations are a different network than TAWES
                hist_stations = fetch_station_metadata("klima-v2-1d")
                hist_nearest = find_nearest_station(lat, lon, hist_stations)
                hist_station_id = hist_nearest["id"] if hist_nearest else (nearest["id"] if nearest else None)
                historical = fetch_historical(hist_station_id, missing_past[0], missing_past[-1]) if hist_station_id else []
                hist_by_date = {d.date: d for d in historical}
                for d in missing_past:
                    if d in hist_by_date:
                        day_forecasts.append(hist_by_date[d])
                day_forecasts.sort(key=lambda f: f.date)

        # Fill remaining gaps (e.g. Sunday) from Open-Meteo 7-day forecast
        sunday = monday + timedelta(days=6)
        week_dates = set(_daterange(monday, sunday))
        covered = {d.date for d in day_forecasts}
        still_missing = week_dates - covered
        if still_missing:
            openmeteo = fetch_openmeteo_daily(lat, lon)
            om_by_date = {d.date: d for d in openmeteo}
            for d in sorted(still_missing):
                if d in om_by_date:
                    day_forecasts.append(om_by_date[d])
            day_forecasts.sort(key=lambda f: f.date)

        # Today's aggregated data
        today_forecast = next((f for f in day_forecasts if f.date == today), None)

        # Current conditions: prefer TAWES, fall back to first forecast point
        if current_obs:
            current_temp = current_obs["TL"]
            wind_dir = _deg_to_compass(current_obs["DD"])
            # FF is in m/s from TAWES
            wind_speed = current_obs["FF"] * 3.6
            # Determine icon: use first forecast sy code (TAWES has no sy)
            current_sy = sy_data[0] if sy_data else 5.0
            current_icon = map_sy_code(current_sy)
        else:
            # Fall back to first NWP point
            current_temp = t2m_data[0] if t2m_data else 0.0
            current_icon = map_sy_code(sy_data[0]) if sy_data else "overcast"
            u = u10m_data[0] if u10m_data else 0.0
            v = v10m_data[0] if v10m_data else 0.0
            wind_speed, wind_dir = wind_speed_and_direction(u, v)

        current_desc = WEATHER_DESCRIPTIONS.get(current_icon, "")

        # Precipitation probability: fraction of forecast hours today with rr_acc > 0
        today_str = datetime.now(timezone.utc).date().isoformat()
        today_precip = [
            rr_acc_data[i] for i, ts in enumerate(timestamps)
            if ts[:10] == today_str
        ]
        if today_precip:
            precip_prob = (sum(1 for v in today_precip if v > 0) / len(today_precip)) * 100
        else:
            precip_prob = 0.0

        temp_min_today = today_forecast.temp_min if today_forecast else current_temp
        temp_max_today = today_forecast.temp_max if today_forecast else current_temp

        weather = WeatherData(
            current_temp=current_temp,
            current_icon=current_icon,
            current_desc=current_desc,
            wind_speed=wind_speed,
            wind_direction=wind_dir,
            precip_probability=precip_prob,
            temp_min_today=temp_min_today,
            temp_max_today=temp_max_today,
            week=day_forecasts,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        _save_cache(weather)
        return weather

    # Forecast failed — try cache
    cached = _load_cache()
    if cached is not None:
        logger.warning("Using cached weather data")
        return cached

    # Everything failed
    logger.error("All weather sources failed for (%.4f, %.4f)", lat, lon)
    return WeatherData(
        current_temp=0.0,
        current_icon="overcast",
        current_desc="",
        wind_speed=0.0,
        wind_direction="N",
        precip_probability=0.0,
        temp_min_today=0.0,
        temp_max_today=0.0,
        error="Wetterdaten nicht verfügbar",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
