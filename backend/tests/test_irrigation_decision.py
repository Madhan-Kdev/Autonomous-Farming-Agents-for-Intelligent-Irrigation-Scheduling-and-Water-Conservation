"""
Phase 10 — Irrigation Decision Agent tests.

Tests cover:
1. Multi-factor decision rules:
   - Postponement for rainfall, wind drift, frost, and soil saturation.
   - Requirement prioritization: CRITICAL, HIGH, and MEDIUM.
   - Rejection/Not Required: optimal soil moisture.
   - Volume clamping between min_irrigation_mm and max_irrigation_mm.
2. IrrigationDecisionAgent execution against AgentState.
3. Database logging into IrrigationRecord.
4. BaseAgent error containment and execution tracking.
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
# Shared fixtures
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
def demo_decision_state(db):
    """AgentState with full multi-agent upstream context."""
    from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
    from app.schemas.agent_state import (
        AgentState,
        CropContext,
        ET0Context,
        HistoricalContext,
        RequestContext,
        SoilContext,
        WeatherContext,
    )

    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zone = ZoneRepository(db).get_active_zones(field.id)[0]

    state = AgentState()
    state.request = RequestContext(farm_id=farm.id, field_id=field.id, zone_ids=[zone.id])
    state.weather = WeatherContext(
        temperature_c=28.0,
        rainfall_mm=0.0,
        forecast_rainfall_7d_mm=0.0,
        wind_speed_ms=2.0,
        irrigation_suitable=True,
    )
    state.soil = SoilContext(
        soil_moisture_pct=14.0,
        field_capacity_pct=25.0,
        wilting_point_pct=10.0,
        available_water_pct=26.7,
        water_holding_capacity_mm=45.0,
        soil_stress_index=0.60,
        is_over_wet=False,
        is_over_dry=False,
    )
    state.crop = CropContext(
        crop_type="Wheat",
        growth_stage="mid",
        crop_coefficient_kc=1.15,
        crop_water_requirement_mm=5.75,
    )
    state.et0 = ET0Context(et0_reference_mm=5.0, etc_mm=5.75)
    state.historical = HistoricalContext(
        avg_rainfall_30d_mm=0.5,
        avg_irrigation_7d_mm=3.0,
    )
    return state, zone


# ================================================================== #
# 1. Decision Rules Engine Unit Tests
# ================================================================== #

class TestIrrigationRulesEngine:

    def test_postponed_for_impending_rain(self):
        from app.schemas.agent_state import IrrigationDecision
        from app.service.irrigation_rules import evaluate_irrigation_decision

        outcome = evaluate_irrigation_decision(
            weather_suitable=True,
            rainfall_forecast_mm=8.0,
            soil_stress_index=0.5,
            available_water_pct=30.0,
        )
        assert outcome.decision == IrrigationDecision.POSTPONED
        assert outcome.recommended_volume_mm == 0.0
        assert "rainfall" in outcome.postponement_reason.lower()

    def test_postponed_for_high_wind(self):
        from app.schemas.agent_state import IrrigationDecision
        from app.service.irrigation_rules import evaluate_irrigation_decision

        outcome = evaluate_irrigation_decision(
            weather_suitable=True,
            wind_speed_ms=10.5,  # > 8.0 m/s threshold
            soil_stress_index=0.5,
            available_water_pct=30.0,
        )
        assert outcome.decision == IrrigationDecision.POSTPONED
        assert "wind" in outcome.postponement_reason.lower()

    def test_postponed_for_frost_risk(self):
        from app.schemas.agent_state import IrrigationDecision
        from app.service.irrigation_rules import evaluate_irrigation_decision

        outcome = evaluate_irrigation_decision(
            weather_suitable=True,
            temperature_c=1.0,  # <= 2.0 °C frost threshold
            soil_stress_index=0.5,
            available_water_pct=30.0,
        )
        assert outcome.decision == IrrigationDecision.POSTPONED
        assert "frost" in outcome.postponement_reason.lower() or "temperature" in outcome.postponement_reason.lower()

    def test_postponed_for_saturated_soil(self):
        from app.schemas.agent_state import IrrigationDecision
        from app.service.irrigation_rules import evaluate_irrigation_decision

        outcome = evaluate_irrigation_decision(
            weather_suitable=True,
            is_over_wet=True,
        )
        assert outcome.decision == IrrigationDecision.POSTPONED
        assert "saturated" in outcome.postponement_reason.lower() or "field capacity" in outcome.postponement_reason.lower()

    def test_required_critical_priority_severe_drought(self):
        from app.schemas.agent_state import IrrigationDecision, IrrigationPriority
        from app.service.irrigation_rules import evaluate_irrigation_decision

        outcome = evaluate_irrigation_decision(
            weather_suitable=True,
            is_over_dry=True,
            soil_stress_index=0.85,
            available_water_pct=15.0,
            water_holding_capacity_mm=40.0,
        )
        assert outcome.decision == IrrigationDecision.REQUIRED
        assert outcome.priority == IrrigationPriority.CRITICAL
        assert outcome.recommended_volume_mm > 0.0

    def test_required_high_priority_active_growth_stress(self):
        from app.schemas.agent_state import IrrigationDecision, IrrigationPriority
        from app.service.irrigation_rules import evaluate_irrigation_decision

        outcome = evaluate_irrigation_decision(
            weather_suitable=True,
            is_over_dry=False,
            soil_stress_index=0.50,
            available_water_pct=35.0,
            crop_growth_stage="mid",
        )
        assert outcome.decision == IrrigationDecision.REQUIRED
        assert outcome.priority == IrrigationPriority.HIGH
        assert outcome.recommended_volume_mm > 0.0

    def test_not_required_when_moisture_adequate(self):
        from app.schemas.agent_state import IrrigationDecision, IrrigationPriority
        from app.service.irrigation_rules import evaluate_irrigation_decision

        outcome = evaluate_irrigation_decision(
            weather_suitable=True,
            is_over_dry=False,
            is_over_wet=False,
            soil_stress_index=0.0,
            available_water_pct=75.0,
        )
        assert outcome.decision == IrrigationDecision.NOT_REQUIRED
        assert outcome.priority == IrrigationPriority.NONE
        assert outcome.recommended_volume_mm == 0.0

    def test_volume_clamped_to_zone_bounds(self):
        from app.service.irrigation_rules import evaluate_irrigation_decision

        # High depletion requesting more than max
        outcome = evaluate_irrigation_decision(
            weather_suitable=True,
            soil_stress_index=0.60,
            available_water_pct=20.0,
            water_holding_capacity_mm=100.0,
            min_irrigation_mm=5.0,
            max_irrigation_mm=25.0,
        )
        assert outcome.recommended_volume_mm <= 25.0
        assert outcome.recommended_volume_mm >= 5.0


# ================================================================== #
# 2. Irrigation Decision Agent Execution Tests
# ================================================================== #

class TestIrrigationDecisionAgentExecution:

    def test_decision_agent_executes_successfully(self, db, demo_decision_state):
        from app.agents.irrigation.irrigation_decision_agent import IrrigationDecisionAgent
        from app.schemas.agent_state import IrrigationDecision

        state, zone = demo_decision_state
        agent = IrrigationDecisionAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        decision_ctx = result.irrigation_decision
        assert decision_ctx.decision == IrrigationDecision.REQUIRED
        assert decision_ctx.recommended_volume_mm is not None
        assert decision_ctx.recommended_volume_mm > 0.0
        assert zone.id in decision_ctx.affected_zones
        assert len(decision_ctx.decision_factors) >= 1
        assert decision_ctx.confidence >= 0.85

    def test_decision_agent_persists_to_database(self, db, demo_decision_state):
        from app.agents.irrigation.irrigation_decision_agent import IrrigationDecisionAgent
        from app.repositories.repositories import IrrigationRecordRepository

        state, zone = demo_decision_state
        agent = IrrigationDecisionAgent(db=db)
        agent.execute(state)

        repo = IrrigationRecordRepository(db)
        records = repo.get_recent_for_zone(zone.id, limit=5)
        assert len(records) >= 1
        latest = records[0]
        assert latest.decision == "REQUIRED"
        assert latest.recommended_volume_mm > 0.0

    def test_decision_agent_execution_record_logged(self, db, demo_decision_state):
        from app.agents.irrigation.irrigation_decision_agent import IrrigationDecisionAgent
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_decision_state
        agent = IrrigationDecisionAgent(db=db)
        result = agent.execute(state)

        dec_records = [
            r for r in result.agent_executions
            if "decision" in r.agent_name.lower() or "irrigation" in r.agent_name.lower()
        ]
        assert len(dec_records) >= 1
        assert dec_records[-1].status == AgentStatus.COMPLETED

    @patch("app.agents.irrigation.irrigation_decision_agent.IrrigationDecisionAgent._run")
    def test_decision_agent_exception_contained(self, mock_run, db, demo_decision_state):
        mock_run.side_effect = RuntimeError("Rules evaluation failure")
        from app.agents.irrigation.irrigation_decision_agent import IrrigationDecisionAgent
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_decision_state
        agent = IrrigationDecisionAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        failed = [r for r in result.agent_executions if r.status == AgentStatus.FAILED]
        assert len(failed) >= 1

