"""
Phase 11 — Zone-Level & Multi-Zone Irrigation Agent tests.

Tests cover:
1. Discovery and independent evaluation of multiple active zones.
2. Zone-specific crop, soil profile, and irrigation plan generation.
3. Filtering by explicit zone_ids in request context.
4. Correct population of state.zone_plans (list[ZoneIrrigationPlan]).
5. Handling of missing/empty request context.
6. Execution recording and BaseAgent error containment.
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
def multi_zone_state(db):
    """AgentState with farm context spanning all 3 demo zones."""
    from app.repositories.repositories import FarmRepository, FieldRepository
    from app.schemas.agent_state import AgentState, ET0Context, RequestContext, WeatherContext

    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]

    state = AgentState()
    state.request = RequestContext(farm_id=farm.id, field_id=field.id)  # no explicit zone_ids -> all zones
    state.weather = WeatherContext(
        temperature_c=29.0,
        rainfall_mm=0.0,
        forecast_rainfall_7d_mm=0.0,
        wind_speed_ms=2.0,
        irrigation_suitable=True,
    )
    state.et0 = ET0Context(et0_reference_mm=5.0)
    return state, farm, field


# ================================================================== #
# Zone Irrigation Agent Tests
# ================================================================== #

class TestZoneIrrigationAgent:

    def test_multi_zone_discovery_and_execution(self, db, multi_zone_state):
        from app.agents.irrigation.zone_irrigation_agent import ZoneIrrigationAgent

        state, farm, field = multi_zone_state
        agent = ZoneIrrigationAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        assert result.zone_plans is not None
        # Demo farm has 3 zones
        assert len(result.zone_plans) == 3

        # Verify each zone plan has expected fields
        zone_ids = [plan.zone_id for plan in result.zone_plans]
        assert len(set(zone_ids)) == 3  # all distinct zones

        for plan in result.zone_plans:
            assert plan.zone_name != ""
            assert isinstance(plan.irrigation_required, bool)
            assert plan.recommended_volume_mm >= 0.0
            assert plan.confidence >= 0.80
            assert len(plan.evidence) >= 4

    def test_single_zone_filtering_by_request(self, db, multi_zone_state):
        from app.agents.irrigation.zone_irrigation_agent import ZoneIrrigationAgent
        from app.repositories.repositories import ZoneRepository

        state, farm, field = multi_zone_state
        first_zone = ZoneRepository(db).get_active_zones(field.id)[0]
        state.request.zone_ids = [first_zone.id]

        agent = ZoneIrrigationAgent(db=db)
        result = agent.execute(state)

        assert len(result.zone_plans) == 1
        assert result.zone_plans[0].zone_id == first_zone.id

    def test_zone_plan_heterogeneous_crops(self, db, multi_zone_state):
        from app.agents.irrigation.zone_irrigation_agent import ZoneIrrigationAgent

        state, farm, field = multi_zone_state
        state.request.zone_ids = []  # evaluate all

        agent = ZoneIrrigationAgent(db=db)
        result = agent.execute(state)

        # Check evidence reports respective crops (Wheat, Tomato, Maize)
        all_evidence = " ".join(
            " ".join(plan.evidence) for plan in result.zone_plans
        )
        assert "Wheat" in all_evidence or "Tomato" in all_evidence or "Maize" in all_evidence

    def test_zone_agent_empty_request_handles_gracefully(self, db):
        from app.agents.irrigation.zone_irrigation_agent import ZoneIrrigationAgent
        from app.schemas.agent_state import AgentState, RequestContext

        state = AgentState()
        state.request = RequestContext(farm_id=999999)  # nonexistent farm
        agent = ZoneIrrigationAgent(db=db)
        result = agent.execute(state)

        assert result.zone_plans == []
        assert len(result.warnings) >= 1

    def test_zone_agent_execution_record_logged(self, db, multi_zone_state):
        from app.agents.irrigation.zone_irrigation_agent import ZoneIrrigationAgent
        from app.schemas.agent_state import AgentStatus

        state, farm, field = multi_zone_state
        agent = ZoneIrrigationAgent(db=db)
        result = agent.execute(state)

        records = [
            r for r in result.agent_executions
            if "zone" in r.agent_name.lower()
        ]
        assert len(records) >= 1
        assert records[-1].status == AgentStatus.COMPLETED

    @patch("app.agents.irrigation.zone_irrigation_agent.ZoneIrrigationAgent._run")
    def test_zone_agent_exception_contained(self, mock_run, db, multi_zone_state):
        mock_run.side_effect = RuntimeError("Zone telemetry discovery timeout")
        from app.agents.irrigation.zone_irrigation_agent import ZoneIrrigationAgent
        from app.schemas.agent_state import AgentStatus

        state, farm, field = multi_zone_state
        agent = ZoneIrrigationAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        failed = [r for r in result.agent_executions if r.status == AgentStatus.FAILED]
        assert len(failed) >= 1

