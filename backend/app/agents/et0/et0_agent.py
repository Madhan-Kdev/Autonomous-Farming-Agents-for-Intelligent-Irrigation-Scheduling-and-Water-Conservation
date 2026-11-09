"""
ET0 Prediction Module (Machine Learning Agent).

Responsibilities
----------------
1. Extract agro-meteorological feature vectors from WeatherContext or database.
2. Run ML inference using the trained Gradient Boosting ET0 model pipeline.
3. Compare the ML prediction with the analytical FAO-56 Penman-Monteith baseline.
4. Calculate residual errors and prediction confidence scores.
5. Populate ``state.et0.et0_predicted_mm``, ``prediction_model``, and ``prediction_confidence``.
6. Synchronize the prediction into the database ``ET0Record`` entity.

ARCHITECTURAL CONSTRAINT (from project spec):
    This agent writes ONLY to the ``et0`` section of AgentState.
    Predictions are derived from a validated Scikit-Learn ML regression pipeline
    trained against FAO-56 physics ground truth.
    LLMs are NEVER used to predict or generate numerical ET0 values.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base.agent_types import AgentType
from app.agents.base.base_agent import BaseAgent
from app.ml.et0_model import get_et0_model
from app.repositories.repositories import (
    ET0RecordRepository,
    FarmRepository,
    FieldRepository,
    WeatherRecordRepository,
    ZoneRepository,
)
from app.schemas.agent_state import AgentState, ET0Context

logger = logging.getLogger(__name__)


class ET0PredictionModule(BaseAgent):
    """
    ET0 Prediction Module Agent.

    Generates empirical ML-based reference evapotranspiration predictions
    using a Gradient Boosting model pipeline.

    Writes to
    ---------
    * ``state.et0`` — ET0Context (updates et0_predicted_mm, prediction_model, prediction_confidence)

    Configuration keys
    ------------------
    ``db`` : SQLAlchemy Session (required)
    """

    name = AgentType.ET0.value
    timeout_seconds = 30.0

    def __init__(self, db: Session, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._db = db
        self._ml_model = get_et0_model()
        self._et0_repo = ET0RecordRepository(db)
        self._weather_repo = WeatherRecordRepository(db)
        self._farm_repo = FarmRepository(db)
        self._field_repo = FieldRepository(db)
        self._zone_repo = ZoneRepository(db)

    # ------------------------------------------------------------------ #
    # Core agent logic
    # ------------------------------------------------------------------ #

    def _run(self, state: AgentState) -> AgentState:
        """
        Execute ET0 Machine Learning Prediction pipeline.

        Steps:
        1. Extract meteorological inputs from state.weather or database.
        2. Run ML inference to predict ET0 in mm/day.
        3. Evaluate residual difference vs FAO-56 PM reference (if available).
        4. Populate state.et0.
        5. Persist prediction to ET0Record in database.
        """
        target_date = (
            state.request.target_date if (state.request and state.request.target_date) else date.today()
        )
        doy = target_date.timetuple().tm_yday

        # Step 1: Collect weather features
        weather_data = self._extract_weather_features(state, target_date)

        self._log_info("ET0PredictionModule: running ML prediction for date=%s (DOY=%d)", target_date, doy)

        # Step 2: Run ML inference
        pred_et0, confidence = self._ml_model.predict(weather_data, day_of_year=doy)

        # Step 3: Ensure state.et0 exists
        if state.et0 is None:
            state.et0 = ET0Context()

        state.et0.et0_predicted_mm = pred_et0
        state.et0.prediction_model = self._ml_model.model_name
        state.et0.prediction_confidence = confidence

        # Step 4: Compare with analytical FAO-56 PM baseline if present
        ref_et0 = state.et0.et0_reference_mm
        evidence_item = f"ML Predicted ET0: {pred_et0:.2f} mm/day via {self._ml_model.model_name} (Confidence: {confidence:.2f})"
        state.et0.evidence.append(evidence_item)

        if ref_et0 is not None:
            diff = abs(pred_et0 - ref_et0)
            ape = (diff / ref_et0 * 100.0) if ref_et0 > 0 else 0.0
            comparison_note = (
                f"Benchmark comparison: Analytical FAO-56 PM = {ref_et0:.2f} mm/day, "
                f"ML Prediction = {pred_et0:.2f} mm/day (Δ = {diff:.2f} mm/day, {ape:.1f}% deviation)"
            )
            state.et0.evidence.append(comparison_note)
            self._log_info(
                "ET0PredictionModule: Analytical=%.2f mm, ML=%.2f mm, Difference=%.2f mm",
                ref_et0,
                pred_et0,
                diff,
            )
        else:
            state.et0.evidence.append("Analytical FAO-56 PM reference not provided in state; ML prediction standalone.")

        # Step 5: Update database ET0Record if zone and farm are known
        self._sync_et0_record(state, target_date, pred_et0, ref_et0)

        self._log_info(
            "ET0PredictionModule: complete — Predicted ET0=%.2f mm/day, Confidence=%.2f",
            pred_et0,
            confidence,
        )
        return state

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #

    def _extract_weather_features(self, state: AgentState, target_date: date) -> dict[str, Any]:
        """Extract weather variables from state.weather or database."""
        weather_dict: dict[str, Any] = {}

        # First priority: check state.weather
        if state.weather:
            w = state.weather
            weather_dict["temperature_mean_c"] = w.temperature_c
            weather_dict["humidity_mean_pct"] = w.humidity_pct
            weather_dict["wind_speed_m_s"] = w.wind_speed_ms
            weather_dict["solar_radiation_mj_m2"] = w.solar_radiation_mjm2
            weather_dict["precipitation_mm"] = w.rainfall_mm

        # Second priority: check database WeatherRecord if farm_id is available
        farm_id = state.request.farm_id if state.request else None
        if farm_id:
            record = self._weather_repo.get_for_date(farm_id, target_date)
            if record:
                if weather_dict.get("temperature_max_c") is None:
                    weather_dict["temperature_max_c"] = record.temperature_max_c
                if weather_dict.get("temperature_min_c") is None:
                    weather_dict["temperature_min_c"] = record.temperature_min_c
                if weather_dict.get("temperature_mean_c") is None:
                    weather_dict["temperature_mean_c"] = record.temperature_mean_c
                if weather_dict.get("humidity_mean_pct") is None:
                    weather_dict["humidity_mean_pct"] = record.humidity_mean_pct
                if weather_dict.get("wind_speed_m_s") is None:
                    weather_dict["wind_speed_m_s"] = record.wind_speed_m_s
                if weather_dict.get("solar_radiation_mj_m2") is None:
                    weather_dict["solar_radiation_mj_m2"] = record.solar_radiation_mj_m2
                if weather_dict.get("pressure_kpa") is None:
                    weather_dict["pressure_kpa"] = record.pressure_kpa

        return weather_dict

    def _sync_et0_record(
        self, state: AgentState, target_date: date, pred_et0: float, ref_et0: float | None
    ) -> None:
        """Persist or update ET0Record in PostgreSQL database."""
        req = state.request
        if not req:
            return

        farm_id = req.farm_id
        zone_id = req.zone_ids[0] if req.zone_ids else None

        if not zone_id and req.field_id:
            zones = self._zone_repo.get_active_zones(req.field_id)
            if zones:
                zone_id = zones[0].id

        if not zone_id and farm_id:
            fields = self._field_repo.get_by_farm(farm_id)
            for f in fields:
                zones = self._zone_repo.get_active_zones(f.id)
                if zones:
                    zone_id = zones[0].id
                    break

        if not zone_id or not farm_id:
            return

        try:
            existing = self._et0_repo.get_for_date(zone_id, target_date)
            if existing:
                existing.et0_ml_predicted_mm = pred_et0
                self._db.flush()
            else:
                self._et0_repo.create(
                    zone_id=zone_id,
                    farm_id=farm_id,
                    record_date=target_date,
                    et0_penman_monteith_mm=ref_et0,
                    et0_ml_predicted_mm=pred_et0,
                    kc_used=state.crop.crop_coefficient_kc if state.crop else None,
                    etc_mm=state.et0.etc_mm if state.et0 else None,
                    computation_method="ML_GRADIENT_BOOSTING",
                )
        except Exception as exc:
            logger.warning("Could not sync ET0Record with ML prediction: %s", exc)
            self._db.rollback()

