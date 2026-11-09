"""
Phase 14 — Farmer Advisory & Explainable AI (XAI) Agent tests.

Tests cover:
1. Advisory synthesis when irrigation is REQUIRED (volume, timing, priority, evidence attribution).
2. Advisory synthesis when irrigation is POSTPONED (reason, weather/rain influence, guidance).
3. Advisory synthesis when irrigation is NOT_REQUIRED (optimal conditions, water savings).
4. Multi-factor attribution verification (Weather, Soil, Crop, ET0, Rainfall, Risk, Water Conservation).
5. Explainable full rationale text generation without hallucinations.
6. Confidence computation and zone targeting.
7. FarmerAdvisoryAgent end-to-end execution, state update (state.advisory), and BaseAgent error containment.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://postgres:FarmAgent2024!@localhost:5432/autonomous_farming"
)
os.environ["DEBUG"] = "false"


# ================================================================== #
# Fixtures
# ================================================================== #

@pytest.fixture(scope="module")
def db():
    from app.core.config import _reset_settings
    _reset_settings()
    from app.database.engine import SessionLocal
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def demo_advisory_state(db):
    """Complete multi-agent AgentState ready for advisory synthesis."""
    from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
    from app.schemas.agent_state import (
        AgentState,
        CropContext,
        ET0Context,
        HistoricalContext,
        IrrigationDecision,
        IrrigationDecisionContext,
        IrrigationPriority,
        OptimizationContext,
        RequestContext,
        RiskContext,
        RiskItem,
        RiskSeverity,
        SoilContext,
        WeatherContext,
    )

    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zone = ZoneRepository(db).get_active_zones(field.id)[0]

    state = AgentState()
    state.request = RequestContext(farm_id=farm.id, field_id=field.id, zone_ids=[zone.id])
    state.weather = WeatherContext(
        temperature_c=26.5,
        wind_speed_ms=2.8,
        rainfall_mm=0.0,
        forecast_rainfall_7d_mm=4.0,
        irrigation_suitable=True,
        confidence=0.90,
    )
    state.soil = SoilContext(
        zone_id=zone.id,
        soil_type="Loam",
        soil_moisture_pct=22.0,
        field_capacity_pct=32.0,
        wilting_point_pct=14.0,
        available_water_pct=44.4,
        soil_stress_index=0.25,
        confidence=0.88,
    )
    state.crop = CropContext(
        crop_type="Wheat",
        growth_stage="mid",
        crop_coefficient_kc=1.15,
        crop_water_requirement_mm=5.2,
        confidence=0.92,
    )
    state.et0 = ET0Context(
        et0_reference_mm=4.5,
        et0_predicted_mm=4.6,
        etc_mm=5.2,
    )
    state.historical = HistoricalContext(
        avg_rainfall_30d_mm=45.0,
        avg_irrigation_7d_mm=18.0,
    )
    state.risk = RiskContext(
        risks=[],
        overall_risk_level=RiskSeverity.INFO,
        recommendation_safe=True,
        risk_summary="All parameters within safe operating margins.",
    )
    state.optimization = OptimizationContext(
        baseline_volume_mm=25.0,
        optimized_volume_mm=14.0,
        water_saving_mm=11.0,
        water_saving_pct=44.0,
        over_irrigation_detected=True,
    )
    state.irrigation_decision = IrrigationDecisionContext(
        decision=IrrigationDecision.REQUIRED,
        priority=IrrigationPriority.HIGH,
        recommended_time="06:00 - 09:00",
        recommended_volume_mm=14.0,
        affected_zones=[zone.id],
        confidence=0.91,
    )
    return state, zone


# ================================================================== #
# 1. Unit Tests for Advisory Engine
# ================================================================== #

class TestAdvisoryEngine:
    def test_advisory_synthesis_required_decision(self, demo_advisory_state):
        from app.service.advisory_engine import generate_farmer_advisory

        state, zone = demo_advisory_state
        advisory = generate_farmer_advisory(
            decision_ctx=state.irrigation_decision,
            weather_ctx=state.weather,
            soil_ctx=state.soil,
            crop_ctx=state.crop,
            et0_ctx=state.et0,
            historical_ctx=state.historical,
            risk_ctx=state.risk,
            optimization_ctx=state.optimization,
            target_zones=[zone.id],
        )

        assert advisory.irrigation_required is True
        assert advisory.recommended_volume_mm == 14.0
        assert advisory.recommended_time == "06:00 - 09:00"
        assert "14.0 mm" in advisory.recommended_action
        assert "Wheat" in advisory.crop_influence
        assert "4.50 mm/day" in advisory.et0_influence or "4.5" in advisory.et0_influence
        assert "44.0%" in advisory.water_conservation_summary
        assert advisory.confidence >= 0.85
        assert len(advisory.full_explanation) > 100

    def test_advisory_synthesis_postponed_decision(self, demo_advisory_state):
        from app.schemas.agent_state import IrrigationDecision
        from app.service.advisory_engine import generate_farmer_advisory

        state, zone = demo_advisory_state
        state.irrigation_decision.decision = IrrigationDecision.POSTPONED
        state.irrigation_decision.postponement_reason = "Rainfall of 18 mm predicted within 24 hours"

        advisory = generate_farmer_advisory(
            decision_ctx=state.irrigation_decision,
            weather_ctx=state.weather,
            soil_ctx=state.soil,
            crop_ctx=state.crop,
            et0_ctx=state.et0,
            historical_ctx=state.historical,
            risk_ctx=state.risk,
            optimization_ctx=state.optimization,
        )

        assert advisory.irrigation_required is False
        assert "Postpone irrigation" in advisory.recommended_action
        assert "18 mm predicted" in advisory.recommended_action

    def test_advisory_synthesis_not_required(self, demo_advisory_state):
        from app.schemas.agent_state import IrrigationDecision
        from app.service.advisory_engine import generate_farmer_advisory

        state, zone = demo_advisory_state
        state.irrigation_decision.decision = IrrigationDecision.NOT_REQUIRED

        advisory = generate_farmer_advisory(
            decision_ctx=state.irrigation_decision,
            weather_ctx=state.weather,
            soil_ctx=state.soil,
            crop_ctx=state.crop,
            et0_ctx=state.et0,
            historical_ctx=state.historical,
            risk_ctx=state.risk,
            optimization_ctx=state.optimization,
        )

        assert advisory.irrigation_required is False
        assert "not required" in advisory.recommended_action.lower()

    def test_advisory_handles_missing_contexts_gracefully(self):
        from app.service.advisory_engine import generate_farmer_advisory

        advisory = generate_farmer_advisory(
            decision_ctx=None,
            weather_ctx=None,
            soil_ctx=None,
            crop_ctx=None,
            et0_ctx=None,
            historical_ctx=None,
            risk_ctx=None,
            optimization_ctx=None,
        )
        assert advisory is not None
        assert advisory.irrigation_required is False
        assert "unavailable" in advisory.weather_influence.lower()
        assert "unavailable" in advisory.soil_influence.lower()


# ================================================================== #
# 2. Integration Tests for FarmerAdvisoryAgent Execution
# ================================================================== #

class TestFarmerAdvisoryAgentExecution:
    def test_advisory_agent_executes_successfully(self, db, demo_advisory_state):
        from app.agents.advisory.advisory_agent import FarmerAdvisoryAgent

        state, zone = demo_advisory_state
        agent = FarmerAdvisoryAgent(db=db)
        result = agent.execute(state)

        assert result.advisory is not None
        assert result.advisory.irrigation_required is True
        assert result.advisory.recommended_volume_mm == 14.0
        assert zone.id in result.advisory.target_zones
        assert len(result.advisory.full_explanation) > 0

    def test_advisory_agent_execution_record_logged(self, db, demo_advisory_state):
        from app.agents.advisory.advisory_agent import FarmerAdvisoryAgent
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_advisory_state
        agent = FarmerAdvisoryAgent(db=db)
        result = agent.execute(state)

        records = [
            r for r in result.agent_executions
            if "advisory" in r.agent_name.lower() or "farmer" in r.agent_name.lower()
        ]
        assert len(records) >= 1
        assert records[-1].status == AgentStatus.COMPLETED

    @patch("app.agents.advisory.advisory_agent.FarmerAdvisoryAgent._run")
    def test_advisory_agent_exception_contained(
        self, mock_run, db, demo_advisory_state
    ):
        mock_run.side_effect = RuntimeError("Advisory generation failure")
        from app.agents.advisory.advisory_agent import FarmerAdvisoryAgent
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_advisory_state
        agent = FarmerAdvisoryAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        failed = [r for r in result.agent_executions if r.status == AgentStatus.FAILED]
        assert len(failed) >= 1

