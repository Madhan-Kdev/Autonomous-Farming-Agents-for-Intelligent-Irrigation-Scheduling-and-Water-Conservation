"""
Phase 12 — Water Conservation & Optimization Agent tests.

Tests cover:
1. Water savings calculations (mm, percentage %, and volume in Liters).
2. Complete conservation (100% savings) when irrigation is postponed or not required.
3. Partial precision conservation when dynamic deficit irrigation is scheduled.
4. Over-irrigation prevention detection and under-irrigation safety validation.
5. WaterOptimizationAgent execution, state updates, evidence generation, and BaseAgent error containment.
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
def demo_optimization_state(db):
    """AgentState with demo farm and required irrigation decision."""
    from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
    from app.schemas.agent_state import (
        AgentState,
        CropContext,
        ET0Context,
        IrrigationDecision,
        IrrigationDecisionContext,
        IrrigationPriority,
        RequestContext,
        SoilContext,
        ZoneIrrigationPlan,
    )

    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zone = ZoneRepository(db).get_active_zones(field.id)[0]  # Zone-1 (2.0 ha)

    state = AgentState()
    state.request = RequestContext(farm_id=farm.id, field_id=field.id, zone_ids=[zone.id])
    state.soil = SoilContext(
        soil_stress_index=0.20,
        available_water_pct=40.0,
        water_holding_capacity_mm=40.0,
    )
    state.crop = CropContext(crop_water_requirement_mm=4.5)
    state.et0 = ET0Context(et0_reference_mm=5.0)
    state.irrigation_decision = IrrigationDecisionContext(
        decision=IrrigationDecision.REQUIRED,
        priority=IrrigationPriority.HIGH,
        recommended_volume_mm=15.0,  # 15 mm recommended vs 25 mm baseline
        affected_zones=[zone.id],
    )
    state.zone_plans = [
        ZoneIrrigationPlan(
            zone_id=zone.id,
            zone_name=zone.name,
            irrigation_required=True,
            recommended_volume_mm=15.0,
            priority=IrrigationPriority.HIGH,
        )
    ]
    return state, zone


# ================================================================== #
# 1. Water Optimization Engine Unit Tests
# ================================================================== #

class TestWaterOptimizationEngine:

    def test_precision_partial_savings(self):
        from app.service.water_optimization_engine import compute_water_savings

        # Baseline: 25.0 mm. Optimized: 15.0 mm on 2.0 ha.
        # Savings: 10.0 mm (40.0%).
        # Liters: 10.0 mm * 2.0 ha * 10,000 = 200,000 Liters.
        result = compute_water_savings(
            recommended_volume_mm=15.0,
            is_irrigation_required=True,
            conventional_baseline_depth_mm=25.0,
            farm_or_zone_area_ha=2.0,
        )
        assert result.water_saving_mm == pytest.approx(10.0, abs=0.1)
        assert result.water_saving_pct == pytest.approx(40.0, abs=0.1)
        assert result.water_saving_liters == pytest.approx(200000.0, abs=1.0)
        assert result.under_irrigation_risk is False

    def test_complete_savings_when_irrigation_not_required(self):
        from app.service.water_optimization_engine import compute_water_savings

        # Irrigation not required -> 0 mm applied
        # Baseline: 25.0 mm on 3.0 ha -> 100% saved (25.0 mm, 750,000 Liters)
        result = compute_water_savings(
            recommended_volume_mm=0.0,
            is_irrigation_required=False,
            conventional_baseline_depth_mm=25.0,
            farm_or_zone_area_ha=3.0,
        )
        assert result.water_saving_mm == pytest.approx(25.0, abs=0.1)
        assert result.water_saving_pct == pytest.approx(100.0, abs=0.1)
        assert result.water_saving_liters == pytest.approx(750000.0, abs=1.0)
        assert result.over_irrigation_prevented is True

    def test_under_irrigation_safeguard(self):
        from app.service.water_optimization_engine import compute_water_savings

        # Extreme stress (0.80) but recommended volume (2.0mm) < etc (5.0mm)
        result = compute_water_savings(
            recommended_volume_mm=2.0,
            is_irrigation_required=True,
            conventional_baseline_depth_mm=25.0,
            farm_or_zone_area_ha=1.0,
            soil_stress_index=0.80,
            etc_mm=5.0,
        )
        assert result.under_irrigation_risk is True


# ================================================================== #
# 2. Water Optimization Agent Execution Tests
# ================================================================== #

class TestWaterOptimizationAgentExecution:

    def test_water_optimization_agent_executes_successfully(
        self, db, demo_optimization_state
    ):
        from app.agents.water_optimization.water_optimization_agent import (
            WaterOptimizationAgent,
        )

        state, zone = demo_optimization_state
        agent = WaterOptimizationAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        opt = result.optimization
        assert opt.baseline_volume_mm == 25.0
        assert opt.optimized_volume_mm == 15.0
        assert opt.water_saving_mm == 10.0
        assert opt.water_saving_pct == 40.0
        assert opt.over_irrigation_detected is True
        assert opt.under_irrigation_risk is False
        assert len(opt.evidence) >= 4

    def test_water_optimization_100_percent_savings_on_postponement(
        self, db, demo_optimization_state
    ):
        from app.agents.water_optimization.water_optimization_agent import (
            WaterOptimizationAgent,
        )
        from app.schemas.agent_state import IrrigationDecision

        state, zone = demo_optimization_state
        # Postpone decision due to rain
        state.irrigation_decision.decision = IrrigationDecision.POSTPONED
        state.irrigation_decision.recommended_volume_mm = 0.0

        agent = WaterOptimizationAgent(db=db)
        result = agent.execute(state)

        opt = result.optimization
        assert opt.optimized_volume_mm == 0.0
        assert opt.water_saving_mm == 25.0
        assert opt.water_saving_pct == 100.0

    def test_water_optimization_execution_record_logged(
        self, db, demo_optimization_state
    ):
        from app.agents.water_optimization.water_optimization_agent import (
            WaterOptimizationAgent,
        )
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_optimization_state
        agent = WaterOptimizationAgent(db=db)
        result = agent.execute(state)

        records = [
            r for r in result.agent_executions
            if "water" in r.agent_name.lower() or "optimization" in r.agent_name.lower()
        ]
        assert len(records) >= 1
        assert records[-1].status == AgentStatus.COMPLETED

    @patch(
        "app.agents.water_optimization.water_optimization_agent.WaterOptimizationAgent._run"
    )
    def test_water_optimization_exception_contained(
        self, mock_run, db, demo_optimization_state
    ):
        mock_run.side_effect = RuntimeError("Optimization calculation exception")
        from app.agents.water_optimization.water_optimization_agent import (
            WaterOptimizationAgent,
        )
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_optimization_state
        agent = WaterOptimizationAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        failed = [r for r in result.agent_executions if r.status == AgentStatus.FAILED]
        assert len(failed) >= 1
