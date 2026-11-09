"""
Weather Intelligence Agent.

Responsibilities
----------------
1. Fetch and persist weather data from NASA POWER (primary source).
2. Compute FAO-56 Penman-Monteith ET₀ for all active zones.
3. Assess weather-based irrigation suitability (rain risk, wind, storm).
4. Populate ``state.weather`` and ``state.et0`` in the shared AgentState.

ARCHITECTURAL CONSTRAINT (from project spec):
    This agent sets ONLY the ``weather`` and ``et0`` sections of AgentState.
    ALL numerical values come from validated API data or the FAO-56 calculator.
    LLM is used ONLY to generate the human-readable ``weather_summary`` text.
    LLM output NEVER sets any float/int field.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base.agent_types import AgentType
from app.agents.base.base_agent import BaseAgent
from app.core.exceptions import NASAPOWERError
from app.repositories.repositories import FarmRepository, WeatherRecordRepository
from app.schemas.agent_state import AgentState, ET0Context, WeatherContext
from app.service.et0_calculator import FAO56PenmanMonteith, build_et0_inputs
from app.service.nasa_power_client import NASAPOWERClient
from app.service.weather_data_service import WeatherDataService, validate_weather_record

logger = logging.getLogger(__name__)


# ================================================================== #
# Weather risk thresholds (all dimensioned, all validated)
# ================================================================== #

class _Thresholds:
    """Weather-based irrigation suitability thresholds."""

    # Irrigation is NOT suitable if rainfall exceeds this (mm/day)
    RAIN_UNSUITABLE_MM = 10.0
    # Irrigation is at risk if rainfall forecast > this (mm in 24h)
    RAIN_RISK_MM = 5.0
    # High wind makes overhead irrigation inefficient (m/s)
    WIND_HIGH_MS = 5.0
    # Very high wind: sprinkler/overhead irrigation should be stopped (m/s)
    WIND_VERY_HIGH_MS = 8.0
    # Low temperature: frost risk, irrigation may cause damage (°C)
    TEMP_FROST_C = 2.0
    # Extreme heat: irrigation efficiency drops, evaporative loss high (°C)
    TEMP_EXTREME_C = 42.0
    # Recent precipitation window for "already rained enough" check (days)
    RECENT_RAIN_WINDOW_DAYS = 3
    RECENT_RAIN_THRESHOLD_MM = 15.0


class WeatherAgent(BaseAgent):
    """
    Weather Intelligence Agent.

    Fetches weather from NASA POWER, computes ET₀, and evaluates
    irrigation suitability based on current and forecast conditions.

    Writes to
    ---------
    * ``state.weather`` — WeatherContext
    * ``state.et0``     — ET0Context

    Configuration keys
    ------------------
    ``db``: SQLAlchemy Session (required)
    ``days_back``: int — days of history to fetch (default: 3)
    ``use_fallback_simulation``: bool — use simulated data if API fails
    """

    name = AgentType.WEATHER.value
    timeout_seconds = 60.0

    def __init__(self, db: Session, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._db = db
        self._days_back: int = self.config.get("days_back", 3)
        self._use_fallback: bool = self.config.get("use_fallback_simulation", True)
        self._nasa_client = NASAPOWERClient()
        self._et0_calc = FAO56PenmanMonteith()
        self._farm_repo = FarmRepository(db)
        self._weather_repo = WeatherRecordRepository(db)

    # ------------------------------------------------------------------ #
    # Core agent logic
    # ------------------------------------------------------------------ #

    def _run(self, state: AgentState) -> AgentState:
        """
        Execute weather intelligence pipeline.

        Steps:
        1. Resolve farm from state.request.farm_id
        2. Fetch/refresh weather data from NASA POWER
        3. Get most recent weather record from DB
        4. Compute FAO-56 ET0
        5. Assess irrigation suitability
        6. Populate state.weather and state.et0
        """
        farm_id = state.request.farm_id if state.request else None
        if not farm_id:
            self._add_warning(state, "No farm_id in request — weather agent skipped.")
            state.weather = self._empty_weather("no_farm_id")
            state.et0 = ET0Context()
            return state

        farm = self._farm_repo.get_by_id(farm_id)
        if farm is None:
            self._add_warning(state, f"Farm id={farm_id} not found.")
            state.weather = self._empty_weather("farm_not_found")
            state.et0 = ET0Context()
            return state

        self._log_info("WeatherAgent: fetching data for farm=%d (%s)", farm_id, farm.name)

        # Step 1: Fetch & persist weather from NASA POWER
        weather_data = self._fetch_weather(farm, state)

        # Apply sandbox / scenario overrides if requested
        if state.request:
            req = state.request
            if req.override_temperature_c is not None:
                t = float(req.override_temperature_c)
                weather_data["temperature_mean_c"] = t
                weather_data["temperature_max_c"] = max(weather_data.get("temperature_max_c", t), t + 3.0)
                weather_data["temperature_min_c"] = min(weather_data.get("temperature_min_c", t), t - 3.0)
            if req.override_humidity_pct is not None:
                h = float(req.override_humidity_pct)
                weather_data["humidity_mean_pct"] = h
                weather_data["humidity_max_pct"] = min(100.0, h + 10.0)
                weather_data["humidity_min_pct"] = max(0.0, h - 10.0)
            if req.override_wind_speed_ms is not None:
                weather_data["wind_speed_m_s"] = float(req.override_wind_speed_ms)
            if req.override_rainfall_mm is not None:
                weather_data["precipitation_mm"] = float(req.override_rainfall_mm)
            if req.override_forecast_rainfall_mm is not None:
                weather_data["forecast_rainfall_7d_mm"] = float(req.override_forecast_rainfall_mm)
            if req.override_rain_probability_pct is not None:
                weather_data["rainfall_probability_pct"] = float(req.override_rain_probability_pct)
            if req.override_solar_radiation_mjm2 is not None:
                weather_data["solar_radiation_mj_m2"] = float(req.override_solar_radiation_mjm2)

        # Step 2: Compute ET0
        et0_result = self._compute_et0(weather_data, farm)

        # Step 3: Assess suitability
        weather_ctx = self._build_weather_context(weather_data, farm)

        # Step 4: Set ET0 context
        et0_ctx = self._build_et0_context(et0_result)

        state.weather = weather_ctx
        state.et0 = et0_ctx

        self._log_info(
            "WeatherAgent: complete — ET0=%.2f mm, suitable=%s",
            et0_ctx.et0_reference_mm or 0.0,
            weather_ctx.irrigation_suitable,
        )
        return state

    # ------------------------------------------------------------------ #
    # Data fetching
    # ------------------------------------------------------------------ #

    def _fetch_weather(
        self, farm: Any, state: AgentState
    ) -> dict[str, Any]:
        """
        Attempt NASA POWER fetch. Fall back to most recent DB record or
        simulated data if the API is unreachable.
        """
        target_date = date.today() - timedelta(days=1)

        # Try to fetch from NASA POWER and persist
        try:
            svc = WeatherDataService(self._db)
            svc.fetch_and_store_nasa_power(
                farm_id=farm.id, days_back=self._days_back
            )
        except NASAPOWERError as exc:
            self._add_warning(state, f"NASA POWER unavailable: {exc}")
            self._log_warning("NASA POWER fetch failed: %s", exc)

        # Read most recent record from DB
        record = self._weather_repo.get_for_date(farm.id, target_date)
        if record is None:
            # Try yesterday - 1
            record = self._weather_repo.get_for_date(
                farm.id, target_date - timedelta(days=1)
            )

        if record:
            return {
                "observation_date": record.observation_date,
                "source": record.source,
                "temperature_max_c": record.temperature_max_c,
                "temperature_min_c": record.temperature_min_c,
                "temperature_mean_c": record.temperature_mean_c,
                "humidity_max_pct": record.humidity_max_pct,
                "humidity_min_pct": record.humidity_min_pct,
                "humidity_mean_pct": record.humidity_mean_pct,
                "wind_speed_m_s": record.wind_speed_m_s,
                "solar_radiation_mj_m2": record.solar_radiation_mj_m2,
                "precipitation_mm": record.precipitation_mm,
                "pressure_kpa": record.pressure_kpa,
            }

        # No DB record — use simulation fallback
        if self._use_fallback:
            self._add_warning(state, "Using simulated weather fallback data.")
            return self._simulated_weather(farm)

        self._add_warning(state, "No weather data available for this farm.")
        return {}

    @staticmethod
    def _simulated_weather(farm: Any) -> dict[str, Any]:
        """
        Generate climatologically plausible simulated weather for testing.

        Values are approximate means for the farm's latitude/season.
        This is clearly labelled 'simulated' throughout.
        """
        return {
            "observation_date": date.today() - timedelta(days=1),
            "source": "simulated",
            "temperature_max_c": 30.0,
            "temperature_min_c": 18.0,
            "temperature_mean_c": 24.0,
            "humidity_max_pct": 70.0,
            "humidity_min_pct": 35.0,
            "humidity_mean_pct": 52.0,
            "wind_speed_m_s": 2.0,
            "solar_radiation_mj_m2": 20.0,
            "precipitation_mm": 0.0,
            "pressure_kpa": 101.3,
        }

    # ------------------------------------------------------------------ #
    # ET0 computation
    # ------------------------------------------------------------------ #

    def _compute_et0(
        self, weather: dict[str, Any], farm: Any
    ) -> dict[str, Any]:
        """Compute FAO-56 PM ET0 from weather data dict."""
        if not weather:
            return {"et0_mm": None, "method": "FAO56_PM", "skipped": True}

        obs_date: date = weather.get("observation_date", date.today() - timedelta(days=1))
        doy = obs_date.timetuple().tm_yday

        et0_inputs = build_et0_inputs(
            weather,
            latitude_deg=farm.latitude,
            altitude_m=farm.altitude_m or 0.0,
            day_of_year=doy,
        )

        if et0_inputs is None:
            return {"et0_mm": None, "method": "FAO56_PM", "skipped": True,
                    "reason": "incomplete_inputs"}

        try:
            et0_mm = self._et0_calc.compute(et0_inputs)
            return {"et0_mm": et0_mm, "method": "FAO56_PM", "skipped": False}
        except Exception as exc:
            logger.warning("ET0 computation failed: %s", exc)
            return {"et0_mm": None, "method": "FAO56_PM", "skipped": True,
                    "reason": str(exc)}

    # ------------------------------------------------------------------ #
    # Context builders
    # ------------------------------------------------------------------ #

    def _build_weather_context(
        self, weather: dict[str, Any], farm: Any
    ) -> WeatherContext:
        """Build WeatherContext from fetched/simulated weather data."""
        if not weather:
            return self._empty_weather("no_data")

        precip = weather.get("precipitation_mm") or 0.0
        temp_mean = weather.get("temperature_mean_c")
        temp_max = weather.get("temperature_max_c")
        wind = weather.get("wind_speed_m_s") or 0.0
        source = weather.get("source", "unknown")

        evidence: list[str] = []
        risk_level = "LOW"

        # ── Assess irrigation suitability ──────────────────────────────
        unsuitable_reasons: list[str] = []

        if precip >= _Thresholds.RAIN_UNSUITABLE_MM:
            unsuitable_reasons.append(
                f"Rainfall {precip:.1f}mm exceeds {_Thresholds.RAIN_UNSUITABLE_MM}mm threshold"
            )
            risk_level = "HIGH"
            evidence.append(f"High precipitation: {precip:.1f} mm")

        if wind >= _Thresholds.WIND_VERY_HIGH_MS:
            unsuitable_reasons.append(
                f"Wind {wind:.1f}m/s exceeds very-high threshold ({_Thresholds.WIND_VERY_HIGH_MS}m/s)"
            )
            risk_level = "HIGH"
            evidence.append(f"Very high wind: {wind:.1f} m/s")
        elif wind >= _Thresholds.WIND_HIGH_MS:
            risk_level = max(risk_level, "MEDIUM")
            evidence.append(f"Elevated wind speed: {wind:.1f} m/s")

        if temp_max and temp_max >= _Thresholds.TEMP_EXTREME_C:
            risk_level = max(risk_level, "MEDIUM")
            evidence.append(f"Extreme heat: {temp_max:.1f}°C")

        if temp_mean and temp_mean <= _Thresholds.TEMP_FROST_C:
            unsuitable_reasons.append(f"Frost risk: {temp_mean:.1f}°C")
            risk_level = "HIGH"
            evidence.append(f"Frost risk: {temp_mean:.1f}°C")

        forecast_rain = weather.get("forecast_rainfall_7d_mm")
        rain_prob = weather.get("rainfall_probability_pct")

        if forecast_rain and forecast_rain >= 5.0:
            unsuitable_reasons.append(
                f"Rainfall forecast {forecast_rain:.1f}mm indicates impending precipitation"
            )
            risk_level = "HIGH"
            evidence.append(f"High forecast precipitation: {forecast_rain:.1f} mm")

        if rain_prob and rain_prob >= 70.0 and precip < 1.0:
            evidence.append(f"High rain probability: {rain_prob:.0f}%")

        irrigation_suitable = len(unsuitable_reasons) == 0

        if irrigation_suitable:
            evidence.append("Conditions suitable for irrigation")

        summary_parts = [f"Source: {source}"]
        if temp_mean:
            summary_parts.append(f"Temp: {temp_mean:.1f}°C")
        if precip > 0:
            summary_parts.append(f"Rain: {precip:.1f}mm")
        if forecast_rain:
            summary_parts.append(f"Forecast Rain: {forecast_rain:.1f}mm")
        if wind > 0:
            summary_parts.append(f"Wind: {wind:.1f}m/s")
        if unsuitable_reasons:
            summary_parts.append("NOT suitable: " + "; ".join(unsuitable_reasons))

        return WeatherContext(
            temperature_c=temp_mean,
            humidity_pct=weather.get("humidity_mean_pct"),
            wind_speed_ms=wind,
            rainfall_mm=precip,
            solar_radiation_mjm2=weather.get("solar_radiation_mj_m2"),
            rainfall_probability_pct=rain_prob,
            forecast_rainfall_7d_mm=forecast_rain,
            irrigation_suitable=irrigation_suitable,
            weather_risk_level=risk_level,
            weather_summary="; ".join(summary_parts),
            confidence=0.90 if source != "simulated" else 0.60,
            data_source=source,
            evidence=evidence,
        )

    @staticmethod
    def _build_et0_context(et0_result: dict[str, Any]) -> ET0Context:
        """Build ET0Context from computation result."""
        et0_mm = et0_result.get("et0_mm")
        method = et0_result.get("method", "FAO56_PM")

        evidence = []
        if et0_mm is not None:
            evidence.append(f"FAO-56 PM ET0 = {et0_mm:.3f} mm/day")
            evidence.append("Computed from validated weather inputs (not LLM)")
        else:
            reason = et0_result.get("reason", "unknown")
            evidence.append(f"ET0 not computed: {reason}")

        return ET0Context(
            et0_reference_mm=et0_mm,
            et0_predicted_mm=None,      # filled by ML model in Phase 8
            etc_mm=None,                # filled by IrrigationDecisionAgent
            calculation_method=method,
            prediction_model="",        # filled in Phase 8
            prediction_confidence=0.0,
            evidence=evidence,
        )

    @staticmethod
    def _empty_weather(reason: str) -> WeatherContext:
        return WeatherContext(
            irrigation_suitable=None,
            weather_risk_level="UNKNOWN",
            weather_summary=f"Weather data unavailable: {reason}",
            confidence=0.0,
            data_source="none",
            evidence=[f"Skipped: {reason}"],
        )
