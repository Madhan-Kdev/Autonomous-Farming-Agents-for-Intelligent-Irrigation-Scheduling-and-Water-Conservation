"""
Phase 6 — Soil Moisture Intelligence Agent tests.

Tests cover:
1. Soil physics calculations: TAW, RAW, AW%, Dr, Ks, and Stress Index.
2. Soil moisture conditions: optimal, moderate stress, severe drought, and over-wet/saturation.
3. SoilAgent execution with database records and target zone resolution.
4. Fallback simulation when soil profile is missing.
5. Error recovery and graceful degradation when request context is empty.
6. Execution records and state evidence updates.
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
def demo_farm_state(db):
    """AgentState with demo farm context."""
    from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
    from app.schemas.agent_state import AgentState, RequestContext

    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zone = ZoneRepository(db).get_active_zones(field.id)[0]

    state = AgentState()
    state.request = RequestContext(farm_id=farm.id, field_id=field.id, zone_ids=[zone.id])
    return state, zone


# ================================================================== #
# 1. Soil Physics Unit Tests
# ================================================================== #

class TestSoilPhysicsCalculations:

    def test_taw_and_raw_calculation(self):
        from app.service.soil_physics import compute_soil_water_status

        # Sandy Loam: FC=22%, WP=10%, Zr=0.3m, p=0.5
        # TAW = 10 * (22 - 10) * 0.3 = 36.0 mm
        # RAW = 0.5 * 36.0 = 18.0 mm
        status = compute_soil_water_status(
            moisture_pct=18.0,
            field_capacity_pct=22.0,
            wilting_point_pct=10.0,
            root_depth_m=0.3,
            depletion_fraction_p=0.5,
        )
        assert status.taw_mm == pytest.approx(36.0, abs=0.1)
        assert status.raw_mm == pytest.approx(18.0, abs=0.1)

    def test_optimal_moisture_zero_stress(self):
        from app.service.soil_physics import compute_soil_water_status

        # Moisture = 20% (FC=22%, WP=10%)
        # Depletion = 10 * (22 - 20) * 0.3 = 6.0 mm <= RAW (18.0 mm)
        # Ks must be 1.0, stress index must be 0.0
        status = compute_soil_water_status(
            moisture_pct=20.0,
            field_capacity_pct=22.0,
            wilting_point_pct=10.0,
            root_depth_m=0.3,
            depletion_fraction_p=0.5,
        )
        assert status.ks == 1.0
        assert status.soil_stress_index == 0.0
        assert not status.is_over_wet
        assert not status.is_over_dry
        assert "ADEQUATE" in status.condition_label or "OPTIMAL" in status.condition_label

    def test_moderate_stress_when_depletion_exceeds_raw(self):
        from app.service.soil_physics import compute_soil_water_status

        # Threshold moisture for p=0.5: FC - p*(FC - WP) = 22 - 0.5*(12) = 16.0%
        # Set moisture to 13.0% (below RAW threshold, but above WP=10%)
        status = compute_soil_water_status(
            moisture_pct=13.0,
            field_capacity_pct=22.0,
            wilting_point_pct=10.0,
            root_depth_m=0.3,
            depletion_fraction_p=0.5,
        )
        assert status.ks < 1.0
        assert status.soil_stress_index > 0.0
        assert not status.is_over_dry
        assert "STRESS" in status.condition_label

    def test_severe_drought_at_wilting_point(self):
        from app.service.soil_physics import compute_soil_water_status

        # Moisture <= WP (10.0%)
        status = compute_soil_water_status(
            moisture_pct=9.5,
            field_capacity_pct=22.0,
            wilting_point_pct=10.0,
            root_depth_m=0.3,
            depletion_fraction_p=0.5,
        )
        assert status.ks == 0.0
        assert status.soil_stress_index == 1.0
        assert status.is_over_dry is True
        assert "WILTING" in status.condition_label

    def test_saturation_over_wet_detected(self):
        from app.service.soil_physics import compute_soil_water_status

        # Moisture exceeds field capacity by > 1% (e.g. 25.0% vs FC=22.0%)
        status = compute_soil_water_status(
            moisture_pct=25.0,
            field_capacity_pct=22.0,
            wilting_point_pct=10.0,
            root_depth_m=0.3,
            depletion_fraction_p=0.5,
        )
        assert status.is_over_wet is True
        assert "SATURATED" in status.condition_label or "OVER-WET" in status.condition_label


# ================================================================== #
# 2. Soil Agent Execution Tests
# ================================================================== #

class TestSoilAgentExecution:

    def test_soil_agent_executes_successfully(self, db, demo_farm_state):
        from app.agents.soil.soil_agent import SoilAgent
        state, zone = demo_farm_state

        agent = SoilAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        assert result.soil is not None
        assert result.soil.zone_id == zone.id
        assert result.soil.soil_moisture_pct is not None
        assert result.soil.water_holding_capacity_mm is not None
        assert 0.0 <= result.soil.soil_stress_index <= 1.0
        assert len(result.soil.evidence) >= 5

    def test_soil_agent_populates_correct_zone_profile(self, db, demo_farm_state):
        from app.agents.soil.soil_agent import SoilAgent
        state, zone = demo_farm_state

        agent = SoilAgent(db=db)
        result = agent.execute(state)

        soil = result.soil
        assert soil.field_capacity_pct == pytest.approx(30.0, abs=1.0)
        assert soil.wilting_point_pct == pytest.approx(12.0, abs=1.0)
        assert soil.confidence >= 0.85
        assert soil.data_source == "simulated"

    def test_missing_request_handled_gracefully(self, db):
        from app.agents.soil.soil_agent import SoilAgent
        from app.schemas.agent_state import AgentState

        agent = SoilAgent(db=db)
        state = AgentState()
        result = agent.execute(state)

        assert result.soil is not None
        assert "Unavailable" in result.soil.soil_condition
        assert len(result.warnings) >= 1

    def test_nonexistent_zone_handled_gracefully(self, db):
        from app.agents.soil.soil_agent import SoilAgent
        from app.schemas.agent_state import AgentState, RequestContext

        agent = SoilAgent(db=db)
        state = AgentState()
        state.request = RequestContext(zone_ids=[999999])
        result = agent.execute(state)

        assert result.soil is not None
        assert result.soil.soil_moisture_pct is None
        assert len(result.warnings) >= 1

    def test_soil_agent_execution_record_logged(self, db, demo_farm_state):
        from app.agents.soil.soil_agent import SoilAgent
        from app.schemas.agent_state import AgentStatus
        state, zone = demo_farm_state

        agent = SoilAgent(db=db)
        result = agent.execute(state)

        soil_records = [
            r for r in result.agent_executions
            if "soil" in r.agent_name.lower()
        ]
        assert len(soil_records) >= 1
        assert soil_records[-1].status == AgentStatus.COMPLETED

    @patch("app.agents.soil.soil_agent.SoilAgent._run")
    def test_soil_agent_exception_contained(self, mock_run, db, demo_farm_state):
        mock_run.side_effect = RuntimeError("Simulated database failure")
        from app.agents.soil.soil_agent import SoilAgent
        from app.schemas.agent_state import AgentStatus
        state, zone = demo_farm_state

        agent = SoilAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        failed = [r for r in result.agent_executions if r.status == AgentStatus.FAILED]
        assert len(failed) >= 1

