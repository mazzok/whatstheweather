# tests/test_weather.py
import math
import json
import pytest
from datetime import date, datetime, timezone
from unittest.mock import patch, MagicMock, mock_open

from src.weather import (
    wind_speed_and_direction,
    map_sy_code,
    aggregate_daily_forecast,
    find_nearest_station,
    fetch_station_metadata,
    fetch_forecast,
    fetch_current_weather,
    get_weather,
    _save_cache,
    _load_cache,
    WeatherData,
    DayForecast,
)


# ---------------------------------------------------------------------------
# wind_speed_and_direction
# ---------------------------------------------------------------------------

class TestWindSpeedAndDirection:
    def test_north_wind(self):
        # u=0, v=positive → wind FROM south → blowing north
        # meteorological: wind FROM direction. v>0 means wind blows north, comes from south → "S"
        speed, direction = wind_speed_and_direction(0.0, 10.0)
        assert speed == pytest.approx(36.0, abs=0.1)
        assert direction == "S"

    def test_east_wind(self):
        # u=positive, v=0 → wind blows eastward → comes from west → "W"
        speed, direction = wind_speed_and_direction(10.0, 0.0)
        assert speed == pytest.approx(36.0, abs=0.1)
        assert direction == "W"

    def test_south_wind(self):
        # u=0, v=-10 → wind blows southward → comes from north → "N"
        speed, direction = wind_speed_and_direction(0.0, -10.0)
        assert speed == pytest.approx(36.0, abs=0.1)
        assert direction == "N"

    def test_west_wind(self):
        # u=-10, v=0 → wind blows westward → comes from east → "O"
        speed, direction = wind_speed_and_direction(-10.0, 0.0)
        assert speed == pytest.approx(36.0, abs=0.1)
        assert direction == "O"

    def test_speed_conversion_ms_to_kmh(self):
        # 1 m/s = 3.6 km/h
        speed, _ = wind_speed_and_direction(1.0, 0.0)
        assert speed == pytest.approx(3.6, abs=0.01)

    def test_diagonal_wind_northeast(self):
        # u=10, v=10 → speed = sqrt(200)*3.6, direction from SW
        speed, direction = wind_speed_and_direction(10.0, 10.0)
        expected_speed = math.sqrt(200) * 3.6
        assert speed == pytest.approx(expected_speed, abs=0.1)
        assert direction == "SW"

    def test_zero_wind(self):
        speed, direction = wind_speed_and_direction(0.0, 0.0)
        assert speed == pytest.approx(0.0, abs=0.001)
        # direction can be anything for zero wind, just check it's a valid compass point
        assert direction in ["N", "NO", "O", "SO", "S", "SW", "W", "NW"]


# ---------------------------------------------------------------------------
# map_sy_code
# ---------------------------------------------------------------------------

class TestMapSyCode:
    def test_clear_codes(self):
        assert map_sy_code(1.0) == "clear"
        assert map_sy_code(2.0) == "clear"

    def test_partly_cloudy(self):
        assert map_sy_code(3.0) == "partly_cloudy"

    def test_mostly_cloudy(self):
        assert map_sy_code(4.0) == "mostly_cloudy"

    def test_overcast(self):
        assert map_sy_code(5.0) == "overcast"

    def test_fog(self):
        assert map_sy_code(6.0) == "fog"
        assert map_sy_code(7.0) == "fog"

    def test_rain_codes(self):
        assert map_sy_code(9.0) == "rain"
        assert map_sy_code(10.0) == "heavy_rain"

    def test_snow_codes(self):
        assert map_sy_code(14.0) == "light_snow"
        assert map_sy_code(15.0) == "snow"
        assert map_sy_code(16.0) == "heavy_snow"

    def test_thunderstorm_codes(self):
        assert map_sy_code(26.0) == "thunderstorm"
        assert map_sy_code(27.0) == "thunderstorm_rain"
        assert map_sy_code(29.0) == "thunderstorm_hail"

    def test_unknown_code_returns_overcast(self):
        assert map_sy_code(99.0) == "overcast"
        assert map_sy_code(0.0) == "overcast"

    def test_nan_returns_overcast(self):
        assert map_sy_code(float("nan")) == "overcast"


# ---------------------------------------------------------------------------
# aggregate_daily_forecast
# ---------------------------------------------------------------------------

class TestAggregateDailyForecast:
    def _make_timestamps(self, days_offsets_hours):
        """Create ISO timestamps given list of (day_offset, hour) tuples relative to 2026-04-17."""
        base = datetime(2026, 4, 17, tzinfo=timezone.utc)
        result = []
        for day_offset, hour in days_offsets_hours:
            dt = base.replace(day=base.day + day_offset, hour=hour)
            result.append(dt.isoformat())
        return result

    def test_single_day_aggregation(self):
        timestamps = [
            "2026-04-17T06:00+00:00",
            "2026-04-17T12:00+00:00",
            "2026-04-17T18:00+00:00",
        ]
        t2m = [10.0, 20.0, 15.0]
        sy = [1.0, 3.0, 5.0]

        days = aggregate_daily_forecast(timestamps, t2m, sy)

        assert len(days) == 1
        assert days[0].date == date(2026, 4, 17)
        assert days[0].temp_min == pytest.approx(10.0)
        assert days[0].temp_max == pytest.approx(20.0)
        assert days[0].temp_avg == pytest.approx(15.0)
        # Most common sy code: 1→clear, 3→partly_cloudy, 5→overcast — all appear once, first wins or any
        assert days[0].icon in ["clear", "partly_cloudy", "overcast"]

    def test_two_day_aggregation(self):
        timestamps = [
            "2026-04-17T06:00+00:00",
            "2026-04-17T12:00+00:00",
            "2026-04-18T06:00+00:00",
            "2026-04-18T18:00+00:00",
        ]
        t2m = [5.0, 15.0, 8.0, 12.0]
        sy = [1.0, 1.0, 3.0, 3.0]

        days = aggregate_daily_forecast(timestamps, t2m, sy)

        assert len(days) == 2
        assert days[0].date == date(2026, 4, 17)
        assert days[0].temp_min == pytest.approx(5.0)
        assert days[0].temp_max == pytest.approx(15.0)
        assert days[0].icon == "clear"

        assert days[1].date == date(2026, 4, 18)
        assert days[1].temp_min == pytest.approx(8.0)
        assert days[1].temp_max == pytest.approx(12.0)
        assert days[1].icon == "partly_cloudy"

    def test_dominant_icon_most_common(self):
        timestamps = [
            "2026-04-17T00:00+00:00",
            "2026-04-17T06:00+00:00",
            "2026-04-17T12:00+00:00",
            "2026-04-17T18:00+00:00",
        ]
        t2m = [10.0, 12.0, 14.0, 11.0]
        # sy: 9=rain (×3), 1=clear (×1) → dominant = rain
        sy = [9.0, 9.0, 9.0, 1.0]

        days = aggregate_daily_forecast(timestamps, t2m, sy)
        assert days[0].icon == "rain"

    def test_empty_returns_empty(self):
        assert aggregate_daily_forecast([], [], []) == []

    def test_seven_days_returns_up_to_seven(self):
        timestamps = []
        t2m = []
        sy = []
        for day in range(7):
            for hour in [6, 12, 18]:
                timestamps.append(f"2026-04-{17 + day:02d}T{hour:02d}:00+00:00")
                t2m.append(10.0 + day)
                sy.append(1.0)
        days = aggregate_daily_forecast(timestamps, t2m, sy)
        assert len(days) == 7


# ---------------------------------------------------------------------------
# find_nearest_station
# ---------------------------------------------------------------------------

class TestFindNearestStation:
    def _make_station(self, sid, lat, lon, active=True):
        return {"id": sid, "name": f"Station {sid}", "lat": lat, "lon": lon, "is_active": active}

    def test_returns_nearest(self):
        stations = [
            self._make_station("A", 48.0, 16.0),
            self._make_station("B", 48.2, 16.4),  # closer to Vienna
            self._make_station("C", 49.0, 17.0),
        ]
        result = find_nearest_station(48.2082, 16.3738, stations)
        assert result["id"] == "B"

    def test_ignores_inactive_stations(self):
        stations = [
            self._make_station("A", 48.2, 16.37, active=False),  # closest but inactive
            self._make_station("B", 48.5, 16.5, active=True),
        ]
        result = find_nearest_station(48.2082, 16.3738, stations)
        assert result["id"] == "B"

    def test_returns_none_for_empty_list(self):
        assert find_nearest_station(48.2, 16.4, []) is None

    def test_returns_none_if_all_inactive(self):
        stations = [self._make_station("A", 48.2, 16.4, active=False)]
        assert find_nearest_station(48.2, 16.4, stations) is None

    def test_single_active_station(self):
        stations = [self._make_station("X", 47.0, 15.0)]
        result = find_nearest_station(48.0, 16.0, stations)
        assert result["id"] == "X"


# ---------------------------------------------------------------------------
# fetch_station_metadata (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchStationMetadata:
    def test_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stations": [
                {"id": "11035", "name": "Wien-Hohe Warte", "lat": 48.2487, "lon": 16.3564, "is_active": True},
                {"id": "11036", "name": "Wien-Innere Stadt", "lat": 48.2065, "lon": 16.3563, "is_active": True},
            ]
        }
        with patch("src.weather.requests.get", return_value=mock_response):
            stations = fetch_station_metadata()
        assert len(stations) == 2
        assert stations[0]["id"] == "11035"

    def test_http_error_returns_empty(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch("src.weather.requests.get", return_value=mock_response):
            stations = fetch_station_metadata()
        assert stations == []

    def test_exception_returns_empty(self):
        with patch("src.weather.requests.get", side_effect=Exception("network error")):
            stations = fetch_station_metadata()
        assert stations == []


# ---------------------------------------------------------------------------
# fetch_forecast (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchForecast:
    def _make_forecast_response(self):
        return {
            "timestamps": [
                "2026-04-17T09:00+00:00",
                "2026-04-17T10:00+00:00",
                "2026-04-17T11:00+00:00",
            ],
            "features": [{
                "properties": {
                    "parameters": {
                        "t2m": {"data": [15.0, 17.0, 16.0]},
                        "sy": {"data": [1.0, 1.0, 3.0]},
                        "u10m": {"data": [2.0, 3.0, 1.0]},
                        "v10m": {"data": [1.0, 1.0, 2.0]},
                        "rr_acc": {"data": [0.0, 0.1, 0.0]},
                    }
                }
            }]
        }

    def test_success_returns_dict(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self._make_forecast_response()
        with patch("src.weather.requests.get", return_value=mock_response):
            result = fetch_forecast(48.2082, 16.3738)
        assert result is not None
        assert "timestamps" in result
        assert len(result["timestamps"]) == 3

    def test_http_error_returns_none(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch("src.weather.requests.get", return_value=mock_response):
            result = fetch_forecast(48.2082, 16.3738)
        assert result is None

    def test_exception_returns_none(self):
        with patch("src.weather.requests.get", side_effect=Exception("timeout")):
            result = fetch_forecast(48.2082, 16.3738)
        assert result is None


# ---------------------------------------------------------------------------
# fetch_current_weather (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchCurrentWeather:
    def _make_tawes_response(self):
        return {
            "timestamps": ["2026-04-17T09:00+00:00"],
            "features": [{
                "properties": {
                    "parameters": {
                        "TL": {"data": [18.5]},
                        "RF": {"data": [65.0]},
                        "DD": {"data": [270.0]},
                        "FF": {"data": [5.0]},
                        "RR": {"data": [0.0]},
                    }
                }
            }]
        }

    def test_success_returns_dict(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self._make_tawes_response()
        with patch("src.weather.requests.get", return_value=mock_response):
            result = fetch_current_weather("11035")
        assert result is not None
        assert "TL" in result
        assert result["TL"] == pytest.approx(18.5)

    def test_http_error_returns_none(self):
        mock_response = MagicMock()
        mock_response.status_code = 503
        with patch("src.weather.requests.get", return_value=mock_response):
            result = fetch_current_weather("11035")
        assert result is None

    def test_exception_returns_none(self):
        with patch("src.weather.requests.get", side_effect=Exception("timeout")):
            result = fetch_current_weather("11035")
        assert result is None


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class TestCache:
    def _sample_weather(self):
        return WeatherData(
            current_temp=18.5,
            current_icon="clear",
            current_desc="Sonnig",
            wind_speed=18.0,
            wind_direction="W",
            precip_probability=5.0,
            temp_min_today=12.0,
            temp_max_today=22.0,
            week=[
                DayForecast(date=date(2026, 4, 17), temp_min=12.0, temp_max=22.0, temp_avg=17.0, icon="clear")
            ],
            timestamp="2026-04-17T10:00:00",
        )

    def test_save_and_load_roundtrip(self):
        weather = self._sample_weather()
        written = {}

        def fake_open(path, mode="r", **kwargs):
            import io
            if "w" in mode:
                buf = io.StringIO()
                original_close = buf.close

                def capture_close():
                    written["data"] = buf.getvalue()
                    original_close()

                buf.close = capture_close
                return buf
            elif "r" in mode:
                if "data" not in written:
                    raise FileNotFoundError
                return io.StringIO(written["data"])
            raise FileNotFoundError

        with patch("builtins.open", side_effect=fake_open):
            _save_cache(weather)
            loaded = _load_cache()

        assert loaded is not None
        assert loaded.current_temp == pytest.approx(18.5)
        assert loaded.current_icon == "clear"
        assert loaded.wind_direction == "W"
        assert len(loaded.week) == 1
        assert loaded.week[0].date == date(2026, 4, 17)
        assert loaded.week[0].icon == "clear"

    def test_load_cache_missing_file_returns_none(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = _load_cache()
        assert result is None

    def test_load_cache_corrupt_json_returns_none(self):
        import io
        with patch("builtins.open", return_value=io.StringIO("not valid json {")):
            result = _load_cache()
        assert result is None


# ---------------------------------------------------------------------------
# get_weather — fully mocked assembly
# ---------------------------------------------------------------------------

class TestGetWeather:
    def _make_metadata(self):
        return [
            {"id": "11035", "name": "Wien-Hohe Warte", "lat": 48.2487, "lon": 16.3564, "is_active": True},
        ]

    def _make_tawes_data(self):
        return {
            "TL": 18.5,
            "RF": 65.0,
            "DD": 270.0,
            "FF": 5.0,
            "RR": 0.0,
        }

    def _make_forecast_data(self):
        timestamps = []
        t2m_data = []
        sy_data = []
        u10m_data = []
        v10m_data = []
        rr_acc_data = []
        # 3 days × 8 hours
        for day in range(3):
            for hour in range(0, 24, 3):
                timestamps.append(f"2026-04-{17 + day:02d}T{hour:02d}:00+00:00")
                t2m_data.append(15.0 + day)
                sy_data.append(1.0)
                u10m_data.append(3.0)
                v10m_data.append(0.0)
                rr_acc_data.append(0.0)
        return {
            "timestamps": timestamps,
            "features": [{
                "properties": {
                    "parameters": {
                        "t2m": {"data": t2m_data},
                        "sy": {"data": sy_data},
                        "u10m": {"data": u10m_data},
                        "v10m": {"data": v10m_data},
                        "rr_acc": {"data": rr_acc_data},
                    }
                }
            }]
        }

    def test_successful_assembly(self):
        with patch("src.weather.fetch_station_metadata", return_value=self._make_metadata()), \
             patch("src.weather.fetch_current_weather", return_value=self._make_tawes_data()), \
             patch("src.weather.fetch_forecast", return_value=self._make_forecast_data()), \
             patch("src.weather._save_cache"):
            result = get_weather(48.2082, 16.3738)

        assert isinstance(result, WeatherData)
        assert result.current_temp == pytest.approx(18.5)
        assert result.current_icon in ["clear", "partly_cloudy", "overcast"]
        assert result.wind_speed > 0
        assert result.wind_direction in ["N", "NO", "O", "SO", "S", "SW", "W", "NW"]
        assert len(result.week) > 0
        assert result.error == ""

    def test_no_stations_uses_forecast_data(self):
        """When station metadata fails, weather should still return data (from forecast) or error gracefully."""
        with patch("src.weather.fetch_station_metadata", return_value=[]), \
             patch("src.weather.fetch_forecast", return_value=self._make_forecast_data()), \
             patch("src.weather._save_cache"):
            result = get_weather(48.2082, 16.3738)

        assert isinstance(result, WeatherData)
        # Either returns partial data from forecast or error — must not raise
        assert result is not None

    def test_forecast_failure_uses_cache(self):
        """When API completely fails, should try to return cached data."""
        cached = WeatherData(
            current_temp=15.0, current_icon="clear", current_desc="Sonnig",
            wind_speed=10.0, wind_direction="N", precip_probability=0.0,
            temp_min_today=10.0, temp_max_today=20.0,
            timestamp="2026-04-17T08:00:00",
        )
        with patch("src.weather.fetch_station_metadata", return_value=[]), \
             patch("src.weather.fetch_forecast", return_value=None), \
             patch("src.weather._load_cache", return_value=cached):
            result = get_weather(48.2082, 16.3738)

        assert result is not None

    def test_returns_error_on_total_failure(self):
        """When everything fails and no cache, return WeatherData with error set."""
        with patch("src.weather.fetch_station_metadata", return_value=[]), \
             patch("src.weather.fetch_forecast", return_value=None), \
             patch("src.weather._load_cache", return_value=None):
            result = get_weather(48.2082, 16.3738)

        assert isinstance(result, WeatherData)
        assert result.error != ""

    def test_week_sorted_by_date(self):
        with patch("src.weather.fetch_station_metadata", return_value=self._make_metadata()), \
             patch("src.weather.fetch_current_weather", return_value=self._make_tawes_data()), \
             patch("src.weather.fetch_forecast", return_value=self._make_forecast_data()), \
             patch("src.weather._save_cache"):
            result = get_weather(48.2082, 16.3738)

        dates = [d.date for d in result.week]
        assert dates == sorted(dates)

    def test_timestamp_is_set(self):
        with patch("src.weather.fetch_station_metadata", return_value=self._make_metadata()), \
             patch("src.weather.fetch_current_weather", return_value=self._make_tawes_data()), \
             patch("src.weather.fetch_forecast", return_value=self._make_forecast_data()), \
             patch("src.weather._save_cache"):
            result = get_weather(48.2082, 16.3738)

        assert result.timestamp != ""
