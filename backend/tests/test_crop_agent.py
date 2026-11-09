"""
Phase 7 — Crop Intelligence Agent tests.

Tests cover:
1. Crop phenology calculations: FAO-56 stage progression, Kc interpolation, root growth.
2. Crop water requirement: ETc = Kc * ET0 and demand categorization.
3. CropAgent execution on database seeded crops (Wheat, Tomato, Maize).
4. Synchronisation with CropGrowthStage repository and state.et0.etc_mm update.
5. Graceful handling of missing crop specifications or empty request context.
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
def demo_crop_state(db):
    """AgentState with demo farm and Zone-1 (Wheat) context."""
    from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
    from app.schemas.agent_state import AgentState, ET0Context, RequestContext, SoilContext

    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zone = ZoneRepository(db).get_active_zones(field.id)[0]  # Zone-1 (Wheat)

    state = AgentState()
    state.request = RequestContext(farm_id=farm.id, field_id=field.id, zone_ids=[zone.id])
    state.et0 = ET0Context(et0_reference_mm=5.0, calculation_method="FAO56_PM")
    state.soil = SoilContext(soil_stress_index=0.0)
    return state, zone


# ================================================================== #
# 1. Crop Phenology Unit Tests
# ================================================================== #

class TestCropPhenologyCalculations:

    def test_initial_stage_constants(self):
        from app.service.crop_phenology import determine_growth_stage_and_kc

        # Days: ini=20, dev=30, mid=40, late=30
        # DAP = 10 -> initial stage
        status = determine_growth_stage_and_kc(
            days_after_planting=10,
            days_initial=20,
            days_development=30,
            days_mid=40,
            days_late=30,
            kc_initial=0.3,
            kc_mid=1.15,
            kc_end=0.25,
            root_depth_initial_m=0.15,
            root_depth_max_m=1.20,
            et0_mm=4.0,
        )
        assert status.stage_name == "initial"
        assert status.current_kc == pytest.approx(0.3, abs=0.01)
        assert status.current_root_depth_m == pytest.approx(0.15, abs=0.01)
        assert status.etc_mm == pytest.approx(1.2, abs=0.05)  # 0.3 * 4.0
        assert status.water_demand_category == "VERY_LOW" or status.water_demand_category == "LOW"

    def test_development_stage_linear_interpolation(self):
        from app.service.crop_phenology import determine_growth_stage_and_kc

        # DAP = 35 (20 initial + 15 into 30 development = 50% through dev)
        # Expected Kc = 0.3 + 0.5 * (1.15 - 0.3) = 0.725
        status = determine_growth_stage_and_kc(
            days_after_planting=35,
            days_initial=20,
            days_development=30,
            days_mid=40,
            days_late=30,
            kc_initial=0.3,
            kc_mid=1.15,
            kc_end=0.25,
            root_depth_initial_m=0.15,
            root_depth_max_m=1.15,
            et0_mm=4.0,
        )
        assert status.stage_name == "development"
        assert status.current_kc == pytest.approx(0.725, abs=0.02)
        # Root depth: 0.15 + 0.5 * (1.15 - 0.15) = 0.65m
        assert status.current_root_depth_m == pytest.approx(0.65, abs=0.02)

    def test_mid_season_stage_peak(self):
        from app.service.crop_phenology import determine_growth_stage_and_kc

        # DAP = 70 (20 + 30 + 20 into mid)
        # Expected Kc = 1.15 (peak)
        status = determine_growth_stage_and_kc(
            days_after_planting=70,
            days_initial=20,
            days_development=30,
            days_mid=40,
            days_late=30,
            kc_initial=0.3,
            kc_mid=1.15,
            kc_end=0.25,
            root_depth_initial_m=0.15,
            root_depth_max_m=1.20,
            et0_mm=5.0,
        )
        assert status.stage_name == "mid"
        assert status.current_kc == pytest.approx(1.15, abs=0.01)
        assert status.current_root_depth_m == pytest.approx(1.20, abs=0.01)
        assert status.etc_mm == pytest.approx(5.75, abs=0.05)  # 1.15 * 5.0
        assert status.water_demand_category == "HIGH"

    def test_late_season_stage_decline(self):
        from app.service.crop_phenology import determine_growth_stage_and_kc

        # DAP = 105 (20 + 30 + 40 + 15 into 30 late = 50% through late)
        # Expected Kc = 1.15 + 0.5 * (0.25 - 1.15) = 0.70
        status = determine_growth_stage_and_kc(
            days_after_planting=105,
            days_initial=20,
            days_development=30,
            days_mid=40,
            days_late=30,
            kc_initial=0.3,
            kc_mid=1.15,
            kc_end=0.25,
            root_depth_initial_m=0.15,
            root_depth_max_m=1.20,
            et0_mm=4.0,
        )
        assert status.stage_name == "late"
        assert status.current_kc == pytest.approx(0.70, abs=0.02)
        assert status.current_root_depth_m == pytest.approx(1.20, abs=0.01)


# ================================================================== #
# 2. Crop Agent Execution Tests
# ================================================================== #

class TestCropAgentExecution:

    def test_crop_agent_executes_successfully(self, db, demo_crop_state):
        from app.agents.crop.crop_agent import CropAgent
        state, zone = demo_crop_state

        agent = CropAgent(db=db, config={"default_dap": 45})
        result = agent.execute(state)

        assert result is not None
        assert result.crop is not None
        assert result.crop.crop_type == "Wheat"
        assert result.crop.crop_coefficient_kc is not None
        assert result.crop.crop_water_requirement_mm is not None
        assert result.crop.confidence >= 0.85
        assert len(result.crop.evidence) >= 5

    def test_crop_agent_updates_et0_context(self, db, demo_crop_state):
        from app.agents.crop.crop_agent import CropAgent
        state, zone = demo_crop_state

        agent = CropAgent(db=db)
        result = agent.execute(state)

        assert result.et0.etc_mm is not None
        assert result.et0.etc_mm == result.crop.crop_water_requirement_mm

    def test_crop_agent_override_crop_type_in_request(self, db, demo_crop_state):
        from app.agents.crop.crop_agent import CropAgent
        state, zone = demo_crop_state
        state.request.crop_type = "Tomato"

        agent = CropAgent(db=db)
        result = agent.execute(state)

        assert result.crop.crop_type == "Tomato"
        assert result.crop.crop_coefficient_kc > 0.0

    def test_crop_agent_missing_request_handled_gracefully(self, db):
        from app.agents.crop.crop_agent import CropAgent
        from app.schemas.agent_state import AgentState

        agent = CropAgent(db=db)
        state = AgentState()
        result = agent.execute(state)

        assert result.crop is not None
        assert len(result.warnings) >= 1

    def test_crop_agent_execution_record_logged(self, db, demo_crop_state):
        from app.agents.crop.crop_agent import CropAgent
        from app.schemas.agent_state import AgentStatus
        state, zone = demo_crop_state

        agent = CropAgent(db=db)
        result = agent.execute(state)

        crop_records = [
            r for r in result.agent_executions
            if "crop" in r.agent_name.lower()
        ]
        assert len(crop_records) >= 1
        assert crop_records[-1].status == AgentStatus.COMPLETED

    @patch("app.agents.crop.crop_agent.CropAgent._run")
    def test_crop_agent_exception_contained(self, mock_run, db, demo_crop_state):
        mock_run.side_effect = RuntimeError("Agronomic lookup failure")
        from app.agents.crop.crop_agent import CropAgent
        from app.schemas.agent_state import AgentStatus
        state, zone = demo_crop_state

        agent = CropAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        failed = [r for r in result.agent_executions if r.status == AgentStatus.FAILED]
        assert len(failed) >= 1

