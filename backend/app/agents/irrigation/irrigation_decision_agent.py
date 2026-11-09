"""
Irrigation Decision Agent.

Responsibilities
----------------
1. Synthesize multi-agent domain intelligence from Weather, Soil, Crop,
   ET0 Prediction, and Historical agents.
2. Execute multi-criteria agricultural decision logic (postponement vs requirement).
3. Assign prioritized operational urgency (CRITICAL, HIGH, MEDIUM, LOW, NONE).
4. Compute recommended irrigation depth (mm) and application window.
5. Populate ``state.irrigation_decision`` in the shared AgentState.
6. Persist structured decision log to ``IrrigationRecord`` database entity.

ARCHITECTURAL CONSTRAINT (from project spec):
    This agent writes ONLY to the ``irrigation_decision`` section of AgentState.
    ALL decisions and numerical quantities originate from agricultural rules,
    soil water balance equations, and physical constraints — NEVER from LLM hallucinations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base.agent_types import AgentType
from app.agents.base.base_agent import BaseAgent
from app.models.zone import Zone
from app.repositories.repositories import (
    FarmRepository,
    FieldRepository,
    IrrigationRecordRepository,
    ZoneRepository,
)
from app.schemas.agent_state import (
    AgentState,
    IrrigationDecision,
    IrrigationDecisionContext,
    IrrigationPriority,
)
from app.service.irrigation_rules import DecisionOutcome, evaluate_irrigation_decision

logger = logging.getLogger(__name__)


class IrrigationDecisionAgent(BaseAgent):
    """
    Irrigation Decision Agent.

    Fuses agro-meteorological evidence into actionable, safe irrigation directives.

    Writes to
    ---------
    * ``state.irrigation_decision`` — IrrigationDecisionContext

    Configuration keys
    ------------------
    ``db`` : SQLAlchemy Session (required)
    """

    name = AgentType.IRRIGATION_DECISION.value
    timeout_seconds = 30.0

    def __init__(self, db: Session, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._db = db
        self._irrig_repo = IrrigationRecordRepository(db)
        self._zone_repo = ZoneRepository(db)
        self._field_repo = FieldRepository(db)
        self._farm_repo = FarmRepository(db)

    # ------------------------------------------------------------------ #
    # Core agent logic
    # ------------------------------------------------------------------ #

    def _run(self, state: AgentState) -> AgentState:
        """
        Execute multi-factor irrigation decision pipeline.

        Steps:
        1. Resolve target zone and farm properties.
        2. Extract environmental and agronomic states.
        3. Evaluate decision rules engine.
        4. Populate state.irrigation_decision.
        5. Persist audit record in PostgreSQL.
        """
        zone = self._resolve_target_zone(state)
        farm_id = state.request.farm_id if state.request else None

        if not farm_id and zone and zone.field:
            farm_id = zone.field.farm_id

        self._log_info(
            "IrrigationDecisionAgent: evaluating decision for Farm id=%s, Zone id=%s",
            farm_id,
            zone.id if zone else "N/A",
        )

        # Step 2: Extract feature inputs from state
        w = state.weather
        s = state.soil
        c = state.crop
        e = state.et0

        weather_suitable = w.irrigation_suitable if w else None
        precip_mm = w.rainfall_mm or 0.0 if w else 0.0
        forecast_rain_mm = w.forecast_rainfall_7d_mm or 0.0 if w else 0.0
        wind_ms = w.wind_speed_ms or 0.0 if w else 0.0
        temp_c = w.temperature_c if (w and w.temperature_c is not None) else 25.0

        is_over_wet = s.is_over_wet if s else False
        is_over_dry = s.is_over_dry if s else False
        soil_stress = s.soil_stress_index if s else 0.0
        aw_pct = s.available_water_pct if s else 60.0
        whc_mm = s.water_holding_capacity_mm or 36.0 if s else 36.0

        etc_mm = 4.0
        if c and c.crop_water_requirement_mm is not None:
            etc_mm = c.crop_water_requirement_mm
        elif e and e.etc_mm is not None:
            etc_mm = e.etc_mm

        growth_stage = c.growth_stage if c else "mid"

        min_depth = zone.min_irrigation_mm if (zone and zone.min_irrigation_mm) else 5.0
        max_depth = zone.max_irrigation_mm if (zone and zone.max_irrigation_mm) else 35.0

        # Step 3: Run rules engine
        outcome: DecisionOutcome = evaluate_irrigation_decision(
            weather_suitable=weather_suitable,
            precipitation_mm=precip_mm,
            rainfall_forecast_mm=forecast_rain_mm,
            wind_speed_ms=wind_ms,
            temperature_c=temp_c,
            is_over_wet=is_over_wet,
            is_over_dry=is_over_dry,
            soil_stress_index=soil_stress,
            available_water_pct=aw_pct,
            water_holding_capacity_mm=whc_mm,
            etc_mm=etc_mm,
            crop_growth_stage=growth_stage,
            min_irrigation_mm=min_depth,
            max_irrigation_mm=max_depth,
        )

        # Step 4: Populate state.irrigation_decision
        affected_zones = [zone.id] if zone else []

        state.irrigation_decision = IrrigationDecisionContext(
            decision=outcome.decision,
            priority=outcome.priority,
            recommended_time=outcome.recommended_time,
            recommended_volume_mm=outcome.recommended_volume_mm,
            affected_zones=affected_zones,
            postponement_reason=outcome.postponement_reason,
            decision_factors=outcome.decision_factors,
            confidence=outcome.confidence,
        )

        # Step 5: Persist record to database
        if zone and farm_id:
            self._record_decision_in_db(state, zone, farm_id, outcome)

        self._log_info(
            "IrrigationDecisionAgent: decision=%s, priority=%s, volume=%.1f mm, postponement=%s",
            outcome.decision.value,
            outcome.priority.value,
            outcome.recommended_volume_mm,
            outcome.postponement_reason or "None",
        )
        return state

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #

    def _resolve_target_zone(self, state: AgentState) -> Zone | None:
        """Find the relevant zone from request."""
        req = state.request
        if not req:
            return None

        if req.zone_ids:
            return self._zone_repo.get_by_id(req.zone_ids[0])

        if req.field_id:
            zones = self._zone_repo.get_active_zones(req.field_id)
            return zones[0] if zones else None

        if req.farm_id:
            fields = self._field_repo.get_by_farm(req.farm_id)
            for field in fields:
                zones = self._zone_repo.get_active_zones(field.id)
                if zones:
                    return zones[0]

        return None

    def _record_decision_in_db(
        self, state: AgentState, zone: Zone, farm_id: int, outcome: DecisionOutcome
    ) -> None:
        """Persist IrrigationRecord to database."""
        try:
            w = state.weather
            s = state.soil
            c = state.crop
            e = state.et0

            et0_val = e.et0_reference_mm if e and e.et0_reference_mm else (e.et0_predicted_mm if e else None)
            etc_val = c.crop_water_requirement_mm if c else (e.etc_mm if e else None)
            reason = outcome.postponement_reason or (
                outcome.decision_factors[0] if outcome.decision_factors else "Autonomous decision"
            )

            self._irrig_repo.create(
                zone_id=zone.id,
                farm_id=farm_id,
                scheduled_at=datetime.now(timezone.utc),
                decision=outcome.decision.value,
                recommended_volume_mm=outcome.recommended_volume_mm,
                recommended_duration_min=round(outcome.recommended_volume_mm * 12.0, 1),  # estimated flow duration
                actual_volume_mm=None,
                actual_duration_min=None,
                was_applied=False,
                soil_moisture_before_pct=s.soil_moisture_pct if s else None,
                soil_moisture_after_pct=None,
                et0_on_day_mm=et0_val,
                etc_on_day_mm=etc_val,
                precipitation_on_day_mm=w.rainfall_mm if w else None,
                decision_confidence=outcome.confidence,
                irrigation_method=zone.irrigation_method or "drip",
                reasoning_summary=reason,
            )
        except Exception as exc:
            logger.warning("Could not persist IrrigationRecord in database: %s", exc)
            self._db.rollback()

