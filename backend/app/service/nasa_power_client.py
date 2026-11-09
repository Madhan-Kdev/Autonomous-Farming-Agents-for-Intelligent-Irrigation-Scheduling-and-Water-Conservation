"""
NASA POWER API client.

Fetches daily agro-meteorological data from NASA's POWER (Prediction of
Worldwide Energy Resources) API.  No API key is required.

API Reference: https://power.larc.nasa.gov/api/temporal/daily/point

Parameters fetched (all FAO-56 required variables):
- T2M_MAX / T2M_MIN / T2M     : Max/Min/Mean temp at 2m (°C)
- RH2M                         : Relative humidity at 2m (%)
- WS2M                         : Wind speed at 2m (m/s)
- ALLSKY_SFC_SW_DWN            : Solar radiation (MJ/m²/day)
- PRECTOTCORR                  : Precipitation (mm/day)
- PS                            : Surface pressure (kPa)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import requests

from app.core.config import get_settings
from app.core.exceptions import NASAPOWERError

logger = logging.getLogger(__name__)

# NASA POWER parameters needed for FAO-56 Penman-Monteith ET0
_PARAMETERS = ",".join([
    "T2M_MAX", "T2M_MIN", "T2M",
    "RH2M", "RH2M_MAX", "RH2M_MIN",
    "WS2M",
    "ALLSKY_SFC_SW_DWN",
    "PRECTOTCORR",
    "PS",
])

_COMMUNITY = "AG"   # Agroclimatology community
_FORMAT    = "JSON"
_TIMEOUT   = 30     # seconds


class NASAPOWERClient:
    """
    Client for the NASA POWER Daily Point API.

    Fetches agro-meteorological data for a single lat/lon point over a
    date range and returns it as a list of daily dictionaries.

    All numeric conversions are applied here so callers always receive
    values in FAO-56 SI units.

    Example
    -------
    ::

        client = NASAPOWERClient()
        records = client.fetch_daily(lat=18.52, lon=73.86,
                                     start=date(2024,1,1),
                                     end=date(2024,1,31))
    """

    def __init__(self, base_url: str | None = None, timeout: int = _TIMEOUT) -> None:
        settings = get_settings()
        self._base_url = base_url or settings.NASA_POWER_BASE_URL
        self._timeout = timeout

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def fetch_daily(
        self,
        lat: float,
        lon: float,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        """
        Fetch daily weather records from NASA POWER.

        Parameters
        ----------
        lat, lon:
            WGS-84 coordinates of the farm centroid.
        start, end:
            Inclusive date range.  Maximum 366 days per request.

        Returns
        -------
        list[dict]
            One dict per day containing validated weather variables.

        Raises
        ------
        NASAPOWERError
            If the API returns an error or cannot be reached.
        """
        params = {
            "parameters": _PARAMETERS,
            "community": _COMMUNITY,
            "longitude": round(lon, 4),
            "latitude": round(lat, 4),
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": _FORMAT,
        }

        logger.info(
            "NASA POWER: requesting %d days for lat=%.4f lon=%.4f",
            (end - start).days + 1, lat, lon,
        )

        try:
            response = requests.get(
                self._base_url, params=params, timeout=self._timeout
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise NASAPOWERError(
                f"NASA POWER request timed out after {self._timeout}s: {exc}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise NASAPOWERError(f"NASA POWER request failed: {exc}") from exc

        return self._parse_response(response.json())

    def fetch_yesterday(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Convenience: fetch a single day (yesterday)."""
        yesterday = date.today() - timedelta(days=1)
        records = self.fetch_daily(lat, lon, start=yesterday, end=yesterday)
        return records[0] if records else None

    # ------------------------------------------------------------------ #
    # Response parsing
    # ------------------------------------------------------------------ #

    def _parse_response(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Parse the NASA POWER JSON response into a list of daily dicts.

        NASA POWER returns data as parameter → {YYYYMMDD: value} maps.
        We transpose this into a list of daily observations.
        """
        try:
            param_data: dict[str, dict[str, float]] = (
                raw["properties"]["parameter"]
            )
        except (KeyError, TypeError) as exc:
            raise NASAPOWERError(
                f"Unexpected NASA POWER response structure: {exc}"
            ) from exc

        # Get sorted date keys from any parameter.
        sample_param = next(iter(param_data.values()))
        date_keys = sorted(sample_param.keys())

        records = []
        for date_str in date_keys:
            obs_date = date(
                int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
            )

            def _get(param: str) -> float | None:
                val = param_data.get(param, {}).get(date_str)
                # NASA POWER uses -999 for missing data.
                if val is None or val <= -998:
                    return None
                return float(val)

            records.append({
                "observation_date": obs_date,
                "source": "NASA_POWER",
                "temperature_max_c": _get("T2M_MAX"),
                "temperature_min_c": _get("T2M_MIN"),
                "temperature_mean_c": _get("T2M"),
                "humidity_max_pct": _get("RH2M_MAX"),
                "humidity_min_pct": _get("RH2M_MIN"),
                "humidity_mean_pct": _get("RH2M"),
                "wind_speed_m_s": _get("WS2M"),
                # NASA returns MJ/m²/day — already correct for FAO-56
                "solar_radiation_mj_m2": _get("ALLSKY_SFC_SW_DWN"),
                "precipitation_mm": _get("PRECTOTCORR"),
                # NASA returns kPa
                "pressure_kpa": _get("PS"),
            })

        logger.info("NASA POWER: parsed %d daily records.", len(records))
        return records
