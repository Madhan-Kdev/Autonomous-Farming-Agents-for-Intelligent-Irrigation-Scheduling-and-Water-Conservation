"""
OpenWeatherMap API client.

Fetches current weather conditions and 5-day/3-hour forecast data
from the OpenWeatherMap API v2.5.

API Reference: https://openweathermap.org/api

Requires WEATHER_API_KEY in .env.  When the key is a placeholder
("your_weather_api_key_here"), the client raises WeatherAPIError with
a clear message rather than sending invalid requests.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import requests

from app.core.config import get_settings
from app.core.exceptions import WeatherAPIError

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEY = "your_weather_api_key_here"
_TIMEOUT = 15


class OpenWeatherMapClient:
    """
    Client for the OpenWeatherMap Current Weather and Forecast APIs.

    Returns data normalised to FAO-56 SI units (°C, m/s, mm, kPa).

    Example
    -------
    ::

        client = OpenWeatherMapClient()
        current = client.fetch_current(lat=18.52, lon=73.86)
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.WEATHER_API_KEY
        self._base_url = base_url or settings.OPENWEATHER_BASE_URL
        self._timeout = _TIMEOUT

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def fetch_current(self, lat: float, lon: float) -> dict[str, Any]:
        """
        Fetch current weather for a lat/lon point.

        Returns
        -------
        dict
            Normalised weather variables for today.

        Raises
        ------
        WeatherAPIError
            If the API key is invalid/missing or the request fails.
        """
        self._validate_key()
        url = f"{self._base_url}/weather"
        params = {
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "appid": self._api_key,
            "units": "metric",  # °C, m/s
        }
        raw = self._get(url, params)
        return self._parse_current(raw)

    def fetch_forecast_daily(
        self, lat: float, lon: float, days: int = 5
    ) -> list[dict[str, Any]]:
        """
        Fetch 5-day/3-hour forecast and aggregate to daily resolution.

        Returns
        -------
        list[dict]
            One dict per forecast day.
        """
        self._validate_key()
        url = f"{self._base_url}/forecast"
        params = {
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "appid": self._api_key,
            "units": "metric",
            "cnt": min(days * 8, 40),  # 8 slots per day (3h intervals)
        }
        raw = self._get(url, params)
        return self._aggregate_forecast(raw, days)

    # ------------------------------------------------------------------ #
    # HTTP helpers
    # ------------------------------------------------------------------ #

    def _validate_key(self) -> None:
        if not self._api_key or self._api_key == _PLACEHOLDER_KEY:
            raise WeatherAPIError(
                "OpenWeatherMap API key is not configured. "
                "Set WEATHER_API_KEY in your .env file. "
                "Get a free key at: https://openweathermap.org/api"
            )

    def _get(self, url: str, params: dict) -> dict[str, Any]:
        logger.debug("OWM GET %s params=%s", url, {k: v for k, v in params.items() if k != "appid"})
        try:
            response = requests.get(url, params=params, timeout=self._timeout)
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise WeatherAPIError(
                f"OpenWeatherMap request timed out: {exc}"
            ) from exc
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 401:
                raise WeatherAPIError(
                    "OpenWeatherMap API key is invalid or expired. "
                    "Check WEATHER_API_KEY in .env."
                ) from exc
            raise WeatherAPIError(
                f"OpenWeatherMap HTTP error: {exc}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise WeatherAPIError(
                f"OpenWeatherMap request failed: {exc}"
            ) from exc
        return response.json()

    # ------------------------------------------------------------------ #
    # Parsers
    # ------------------------------------------------------------------ #

    def _parse_current(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Parse OWM current weather response."""
        main = raw.get("main", {})
        wind = raw.get("wind", {})
        rain = raw.get("rain", {})
        return {
            "observation_date": date.today(),
            "source": "OpenWeatherMap",
            "temperature_max_c": main.get("temp_max"),
            "temperature_min_c": main.get("temp_min"),
            "temperature_mean_c": main.get("temp"),
            "humidity_mean_pct": main.get("humidity"),
            "humidity_max_pct": None,
            "humidity_min_pct": None,
            "wind_speed_m_s": wind.get("speed"),
            "solar_radiation_mj_m2": None,  # Not provided by OWM current
            "precipitation_mm": rain.get("1h", 0.0),
            # OWM returns hPa → convert to kPa
            "pressure_kpa": (main.get("pressure") or 1013.25) / 10.0,
            "dew_point_c": self._calc_dew_point(
                main.get("temp"), main.get("humidity")
            ),
        }

    def _aggregate_forecast(
        self, raw: dict[str, Any], days: int
    ) -> list[dict[str, Any]]:
        """Aggregate 3-hourly OWM forecast slots into daily records."""
        slots = raw.get("list", [])
        daily: dict[date, dict[str, list[float]]] = {}

        for slot in slots:
            dt = datetime.fromtimestamp(slot["dt"], tz=timezone.utc).date()
            if dt not in daily:
                daily[dt] = {
                    "temps": [], "humidities": [], "winds": [], "rains": []
                }
            main = slot.get("main", {})
            if t := main.get("temp"):
                daily[dt]["temps"].append(t)
            if h := main.get("humidity"):
                daily[dt]["humidities"].append(h)
            if w := slot.get("wind", {}).get("speed"):
                daily[dt]["winds"].append(w)
            daily[dt]["rains"].append(
                slot.get("rain", {}).get("3h", 0.0)
            )

        result = []
        for obs_date in sorted(daily.keys())[:days]:
            d = daily[obs_date]
            temps = d["temps"]
            result.append({
                "observation_date": obs_date,
                "source": "OpenWeatherMap",
                "temperature_max_c": max(temps) if temps else None,
                "temperature_min_c": min(temps) if temps else None,
                "temperature_mean_c": sum(temps) / len(temps) if temps else None,
                "humidity_mean_pct": (
                    sum(d["humidities"]) / len(d["humidities"])
                    if d["humidities"] else None
                ),
                "humidity_max_pct": None,
                "humidity_min_pct": None,
                "wind_speed_m_s": (
                    sum(d["winds"]) / len(d["winds"]) if d["winds"] else None
                ),
                "solar_radiation_mj_m2": None,
                "precipitation_mm": sum(d["rains"]),
                "pressure_kpa": None,
                "dew_point_c": None,
            })
        return result

    @staticmethod
    def _calc_dew_point(temp_c: float | None, rh_pct: float | None) -> float | None:
        """
        Magnus formula dew point approximation.

        Reference: Lawrence (2005), BAMS.
        Valid for 0°C < T < 60°C.
        """
        if temp_c is None or rh_pct is None or rh_pct <= 0:
            return None
        import math
        a, b = 17.625, 243.04
        alpha = (a * temp_c) / (b + temp_c) + math.log(rh_pct / 100.0)
        return round((b * alpha) / (a - alpha), 2)
