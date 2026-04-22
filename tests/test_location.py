# tests/test_location.py
from unittest.mock import patch, MagicMock
from src.location import get_location


def test_get_location_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "lat": 48.2082,
        "lon": 16.3738,
        "city": "Vienna",
    }

    with patch("src.location.requests.get", return_value=mock_response):
        lat, lon, city = get_location()

    assert lat == 48.2082
    assert lon == 16.3738
    assert city == "Vienna"


def test_get_location_missing_city():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "lat": 48.2082,
        "lon": 16.3738,
    }

    with patch("src.location.requests.get", return_value=mock_response):
        lat, lon, city = get_location()

    assert lat == 48.2082
    assert lon == 16.3738
    assert city == ""


def test_get_location_failure_returns_none():
    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch("src.location.requests.get", return_value=mock_response):
        result = get_location()

    assert result is None


def test_get_location_timeout_returns_none():
    with patch("src.location.requests.get", side_effect=Exception("timeout")):
        result = get_location()

    assert result is None
