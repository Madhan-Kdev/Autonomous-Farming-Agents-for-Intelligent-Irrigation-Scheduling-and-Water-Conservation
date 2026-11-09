"""
Weather Data Service — orchestrates data acquisition and persistence.

This service:
1. Fetches weather from NASA POWER (primary) or OpenWeatherMap (secondary).
2. Validates all incoming values (bounds checking, -999 sentinel removal).
3. Computes FAO-56 Penman-Monteith ET0.
4. Persists WeatherRecord and ET0Record to the database.
5. Returns structured results for downstream agents.

ARCHITECTURAL RULE: No LLM output is used at any point in this service.
All numerical values are either fetched from validated APIs or computed
by the FAO-56 analytical equations.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.zone import Zone
from app.repositories.repositories import (
    ET0RecordRepository,
    FarmRepository,
    WeatherRecordRepository,
    ZoneRepository,
)
from app.service.et0_calculator import FAO56PenmanMonteith, build_et0_inputs
from app.service.nasa_power_client import NASAPOWERClient

logger = logging.getLogger(__name__)


# ================================================================== #
# Validation bounds (physical limits)
# ================================================================== #

_BOUNDS: dict[str, tuple[float, float]] = {
    "temperature_max_c":      (-60.0,  60.0),
    "temperature_min_c":      (-60.0,  60.0),
    "temperature_mean_c":     (-60.0,  60.0),
    "humidity_max_pct":       (0.0,   100.0),
    "humidity_min_pct":       (0.0,   100.0),
    "humidity_mean_pct":      (0.0,   100.0),
    "wind_speed_m_s":         (0.0,    80.0),
    "solar_radiation_mj_m2":  (0.0,    50.0),
    "precipitation_mm":       (0.0,   500.0),
    "pressure_kpa":           (60.0,  110.0),
}


def validate_weather_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Validate weather values against physical bounds.

    Out-of-range values are set to None (not silently accepted).
    Returns the cleaned record.
    """
    cleaned = dict(record)
    for field, (lo, hi) in _BOUNDS.items():
        val = cleaned.get(field)
        if val is not None:
            if not (lo <= float(val) <= hi):
                logger.warning(
                    "Weather validation: %s=%s out of range [%s, %s] — set to None",
                    field, val, lo, hi,
                )
                cleaned[field] = None
    return cleaned


# ================================================================== #
# Weather Data Service
# ================================================================== #

class WeatherDataService:
    """
    Orchestrates weather data acquisition, validation, ET0 calculation,
    and database persistence.

    Usage::

        service = WeatherDataService(db)
        result = service.fetch_and_store_nasa_power(farm_id=1, days_back=7)
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._nasa_client = NASAPOWERClient()
        self._et0_calc = FAO56PenmanMonteith()
        self._weather_repo = WeatherRecordRepository(db)
        self._et0_repo = ET0RecordRepository(db)
        self._farm_repo = FarmRepository(db)
        self._zone_repo = ZoneRepository(db)

    # ------------------------------------------------------------------ #
    # Main public methods
    # ------------------------------------------------------------------ #

    def fetch_and_store_nasa_power(
        self,
        farm_id: int,
        days_back: int = 7,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """
        Fetch weather from NASA POWER for a farm and persist to DB.

        Parameters
        ----------
        farm_id:
            ID of the Farm to fetch weather for.
        days_back:
            Number of days before end_date to fetch. Default: 7.
        end_date:
            Last day to fetch (inclusive). Default: yesterday.

        Returns
        -------
        dict
            Summary with counts of records fetched/stored/skipped.
        """
        farm = self._farm_repo.get_by_id(farm_id)
        if farm is None:
            raise ValueError(f"Farm id={farm_id} not found.")

        end = end_date or (date.today() - timedelta(days=1))
        start = end - timedelta(days=days_back - 1)

        logger.info(
            "WeatherDataService: fetching NASA POWER for farm=%d (%s to %s)",
            farm_id, start, end,
        )

        raw_records = self._nasa_client.fetch_daily(
            lat=farm.latitude, lon=farm.longitude,
            start=start, end=end,
        )

        stored, skipped = 0, 0
        for raw in raw_records:
            obs_date: date = raw["observation_date"]

            # Skip if already stored.
            existing = self._weather_repo.get_for_date(farm_id, obs_date)
            if existing:
                skipped += 1
                continue

            cleaned = validate_weather_record(raw)
            self._weather_repo.create(farm_id=farm_id, **cleaned)
            stored += 1

        logger.info(
            "WeatherDataService: stored=%d skipped=%d for farm=%d",
            stored, skipped, farm_id,
        )
        return {"farm_id": farm_id, "stored": stored, "skipped": skipped,
                "start": str(start), "end": str(end)}

    def compute_and_store_et0(
        self,
        farm_id: int,
        zone_id: int,
        target_date: date | None = None,
    ) -> dict[str, Any]:
        """
        Compute FAO-56 ET0 for a zone on a given date and persist.

        Reads WeatherRecord for the farm/date, computes PM-ET0, then
        reads the current CropGrowthStage Kc to derive ETc and NIR.

        Parameters
        ----------
        farm_id:
            Farm ID (used to find the WeatherRecord).
        zone_id:
            Zone ID (used to find the CropGrowthStage and store ET0Record).
        target_date:
            Date to compute ET0 for. Default: yesterday.

        Returns
        -------
        dict
            ET0, ETc, NIR values and metadata.
        """
        target = target_date or (date.today() - timedelta(days=1))

        farm = self._farm_repo.get_by_id(farm_id)
        if farm is None:
            raise ValueError(f"Farm id={farm_id} not found.")

        weather = self._weather_repo.get_for_date(farm_id, target)
        if weather is None:
            logger.warning(
                "No WeatherRecord for farm=%d date=%s — ET0 skipped.", farm_id, target
            )
            return {"skipped": True, "reason": "no_weather_record", "date": str(target)}

        # Skip if ET0 already computed for this zone/date.
        existing = self._et0_repo.get_for_date(zone_id, target)
        if existing:
            return {"skipped": True, "reason": "already_computed", "date": str(target),
                    "et0_mm": existing.et0_penman_monteith_mm}

        # Build inputs.
        weather_dict = {
            "temperature_max_c":     weather.temperature_max_c,
            "temperature_min_c":     weather.temperature_min_c,
            "temperature_mean_c":    weather.temperature_mean_c,
            "humidity_max_pct":      weather.humidity_max_pct,
            "humidity_min_pct":      weather.humidity_min_pct,
            "humidity_mean_pct":     weather.humidity_mean_pct,
            "wind_speed_m_s":        weather.wind_speed_m_s,
            "solar_radiation_mj_m2": weather.solar_radiation_mj_m2,
            "precipitation_mm":      weather.precipitation_mm,
            "pressure_kpa":          weather.pressure_kpa,
        }

        doy = target.timetuple().tm_yday
        et0_inputs = build_et0_inputs(
            weather_dict,
            latitude_deg=farm.latitude,
            altitude_m=farm.altitude_m or 0.0,
            day_of_year=doy,
        )

        if et0_inputs is None:
            logger.warning("ET0 inputs incomplete for farm=%d date=%s.", farm_id, target)
            return {"skipped": True, "reason": "incomplete_inputs", "date": str(target)}

        et0_mm = self._et0_calc.compute(et0_inputs)

        # Get current Kc from CropGrowthStage if available.
        from app.repositories.repositories import CropGrowthStageRepository
        stage = CropGrowthStageRepository(self._db).get_current_for_zone(zone_id)
        kc = stage.current_kc if stage else 1.0
        etc_mm = round(kc * et0_mm, 3)

        # Effective rainfall (USDA SCS method — simplified).
        precip = weather.precipitation_mm or 0.0
        eff_rain = _effective_rainfall(precip)
        nir_mm = round(max(0.0, etc_mm - eff_rain), 3)

        self._et0_repo.create(
            zone_id=zone_id,
            farm_id=farm_id,
            record_date=target,
            et0_penman_monteith_mm=et0_mm,
            et0_ml_predicted_mm=None,      # populated in Phase 8
            kc_used=kc,
            etc_mm=etc_mm,
            effective_rainfall_mm=round(eff_rain, 3),
            net_irrigation_requirement_mm=nir_mm,
            computation_method="FAO56_PM",
        )

        logger.info(
            "ET0 stored: zone=%d date=%s ET0=%.2f mm ETc=%.2f mm NIR=%.2f mm",
            zone_id, target, et0_mm, etc_mm, nir_mm,
        )
        return {
            "zone_id": zone_id,
            "date": str(target),
            "et0_mm": et0_mm,
            "kc": kc,
            "etc_mm": etc_mm,
            "effective_rainfall_mm": round(eff_rain, 3),
            "net_irrigation_requirement_mm": nir_mm,
            "skipped": False,
        }

    def get_recent_weather_summary(
        self, farm_id: int, days: int = 7
    ) -> dict[str, Any]:
        """
        Return a summary of recent weather for a farm (for agent context).

        Returns mean temperature, total precipitation, and mean ET0
        over the last `days` days.
        """
        records = self._weather_repo.get_recent(farm_id, days)
        if not records:
            return {"farm_id": farm_id, "days": days, "records": 0}

        temps = [r.temperature_mean_c for r in records if r.temperature_mean_c]
        precips = [r.precipitation_mm for r in records if r.precipitation_mm]
        winds = [r.wind_speed_m_s for r in records if r.wind_speed_m_s]

        return {
            "farm_id": farm_id,
            "days_requested": days,
            "records_found": len(records),
            "temp_mean_c": round(sum(temps) / len(temps), 2) if temps else None,
            "total_precipitation_mm": round(sum(precips), 2),
            "wind_mean_m_s": round(sum(winds) / len(winds), 2) if winds else None,
            "date_range": {
                "start": str(min(r.observation_date for r in records)),
                "end": str(max(r.observation_date for r in records)),
            },
        }


# ================================================================== #
# USDA SCS Effective Rainfall (simplified)
# ================================================================== #

def _effective_rainfall(precip_mm: float) -> float:
    """
    Estimate effective rainfall using USDA SCS formula (simplified).

    Reference: USDA Soil Conservation Service (1967).
    Effective rainfall is the portion of precipitation that contributes
    to crop water use (excludes runoff and deep percolation).

    For daily totals:
    - If precip <= 25 mm: eff_rain = 0.6 * precip - 10   (>= 0)
    - If precip >  25 mm: eff_rain = 0.8 * precip - 25   (>= 0)
    """
    if precip_mm <= 0:
        return 0.0
    if precip_mm <= 25.0:
        return max(0.0, 0.6 * precip_mm - 10.0)
    return max(0.0, 0.8 * precip_mm - 25.0)

