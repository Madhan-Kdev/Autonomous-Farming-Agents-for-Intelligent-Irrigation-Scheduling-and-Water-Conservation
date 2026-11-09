"""
Risk and Anomaly Agent.

Responsibilities
----------------
1. Ingest multidimensional farm telemetry from AgentState:
   - Weather: temperature, wind speed, precipitation, 7d forecast.
   - Soil: moisture %, field capacity, wilting point, available water %, stress index, over-wet/over-dry flags.
   - Irrigation Decision: irrigation required flag, recommended volume (mm).
   - Zone characteristics: hydraulic absorption capacity / max depth.
2. Run rule-based agro-meteorological, hydraulic, and sensor anomaly diagnostics.
3. Classify detected risks by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO).
4. Evaluate overall operational recommendation safety (`recommendation_safe = True/False`).
5. Populate `state.risk` (`RiskContext`) in the shared AgentState:
   - `risks: list[RiskItem]`
   - `overall_risk_level: RiskSeverity`
   - `recommendation_safe: bool`
   - `risk_summary: str`
6. Log `AgentExecutionRecord` containing execution timing, agent status, and containment.

ARCHITECTURAL CONSTRAINTS:
- Writes ONLY to `state.risk`.
- All risk assessments derive from agro-meteorological rules, sensor limits, and physics — NEVER from LLM hallucinations.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base.agent_types import AgentType
from app.agents.base.base_agent import BaseAgent
from app.repositories.repositories import ZoneRepository
from app.schemas.agent_state import (
    AgentState,
    IrrigationDecision,
    RiskContext,
    RiskItem,
    RiskSeverity,
)
from app.service.risk_engine import RiskEvaluationResult, evaluate_system_risks

logger = logging.getLogger(__name__)


class RiskAnomalyAgent(BaseAgent):
    """
    Risk and Anomaly Agent.

    Evaluates potential hazards across weather, soil, hydraulic, and sensor dimensions.

    Writes to
    ---------
    * ``state.risk`` — RiskContext
    """

    name = AgentType.RISK.value
    timeout_seconds = 30.0

    def __init__(
        self,
        db: Session | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(config)
        self._db = db
        self._zone_repo = ZoneRepository(db) if db else None

    def _run(self, state: AgentState) -> AgentState:
        """
        Execute risk evaluation and populate state.risk.

        Parameters
        ----------
        state : AgentState
            The shared agent state.

        Returns
        -------
        AgentState
            Updated state with state.risk populated.
        """
        self._log_info("RiskAnomalyAgent evaluating system risks")

        w = state.weather
        s = state.soil
        d = state.irrigation_decision

        # 1. Weather parameters
        temp_c = w.temperature_c if (w and w.temperature_c is not None) else None
        wind_ms = w.wind_speed_ms if (w and w.wind_speed_ms is not None) else None
        rain_mm = w.rainfall_mm if (w and w.rainfall_mm is not None) else None
        forecast_rain_mm = w.forecast_rainfall_7d_mm if (w and w.forecast_rainfall_7d_mm is not None) else None

        # 2. Soil parameters
        moisture_pct = s.soil_moisture_pct if (s and s.soil_moisture_pct is not None) else None
        fc_pct = s.field_capacity_pct if (s and s.field_capacity_pct is not None) else None
        wp_pct = s.wilting_point_pct if (s and s.wilting_point_pct is not None) else None
        aw_pct = s.available_water_pct if (s and s.available_water_pct is not None) else None
        stress_idx = s.soil_stress_index if (s and s.soil_stress_index is not None) else None
        is_over_wet = s.is_over_wet if s else False
        is_over_dry = s.is_over_dry if s else False

        # 3. Decision parameters
        irrig_required = False
        recommended_vol_mm = 0.0
        if d:
            irrig_required = d.decision == IrrigationDecision.REQUIRED
            recommended_vol_mm = d.recommended_volume_mm or 0.0

        # 4. Zone capacity limits
        max_capacity_mm = 45.0
        zone_id = None
        if state.request and state.request.zone_ids:
            zone_id = state.request.zone_ids[0]
        elif s and s.zone_id:
            zone_id = s.zone_id

        if zone_id and self._zone_repo:
            try:
                zone = self._zone_repo.get_by_id(zone_id)
                if zone and zone.max_irrigation_mm:
                    max_capacity_mm = zone.max_irrigation_mm
            except Exception as exc:  # noqa: BLE001
                self._log_debug("Could not retrieve zone %s for hydraulic capacity: %s", zone_id, exc)

        # 5. Execute risk diagnostic engine
        result: RiskEvaluationResult = evaluate_system_risks(
            temperature_c=temp_c,
            wind_speed_ms=wind_ms,
            rainfall_mm=rain_mm,
            forecast_rain_7d_mm=forecast_rain_mm,
            soil_moisture_pct=moisture_pct,
            field_capacity_pct=fc_pct,
            wilting_point_pct=wp_pct,
            available_water_pct=aw_pct,
            soil_stress_index=stress_idx,
            is_over_wet=is_over_wet,
            is_over_dry=is_over_dry,
            irrigation_required=irrig_required,
            recommended_volume_mm=recommended_vol_mm,
            max_irrigation_capacity_mm=max_capacity_mm,
        )

        # 6. Populate state.risk
        state.risk = RiskContext(
            risks=result.risks,
            overall_risk_level=result.overall_risk_level,
            recommendation_safe=result.recommendation_safe,
            risk_summary=result.risk_summary,
        )

        self._log_info(
            "RiskAnomalyAgent completed: %d risks found, overall severity=%s, safe=%s",
            len(result.risks),
            result.overall_risk_level.value,
            result.recommendation_safe,
        )
        return state

