"""
Phase 15 — Full LangGraph Multi-Agent Orchestration Workflow tests.

Tests cover:
1. Graph compilation and structure.
2. End-to-end multi-agent workflow invocation with demo farm state.
3. Verification that every specialized agent populates its designated AgentState section:
   - weather (WeatherContext)
   - soil (SoilContext)
   - crop (CropContext)
   - et0 (ET0Context)
   - historical (HistoricalContext)
   - irrigation_decision (IrrigationDecisionContext)
   - zone_plans (list[ZoneIrrigationPlan])
   - optimization (OptimizationContext)
   - risk (RiskContext)
   - advisory (AdvisoryContext)
4. Telemetry and execution chain logging across all 10 nodes.
5. Error containment and graceful pipeline continuation on upstream node failures.
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
def initial_workflow_state(db):
    """Initial state targeting the demo farm."""
    from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
    from app.schemas.agent_state import AgentState, RequestContext

    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zone = ZoneRepository(db).get_active_zones(field.id)[0]

    state = AgentState()
    state.request = RequestContext(
        farm_id=farm.id,
        field_id=field.id,
        zone_ids=[zone.id],
        crop_type="Wheat",
        location_latitude=farm.latitude,
        location_longitude=farm.longitude,
    )
    return state, farm, field, zone


# ================================================================== #
# Tests
# ================================================================== #

class TestAgentWorkflowGraph:
    def test_workflow_graph_compiles(self, db):
        from app.workflow.agent_workflow import create_agent_workflow

        graph = create_agent_workflow(db)
        assert graph is not None

    def test_end_to_end_workflow_execution(self, db, initial_workflow_state):
        from app.schemas.agent_state import AgentState, AgentStatus
        from app.workflow.agent_workflow import create_agent_workflow

        state, farm, field, zone = initial_workflow_state
        graph = create_agent_workflow(db)

        # Invoke full 10-node multi-agent graph
        final_state_raw = graph.invoke(state)
        # In LangGraph with Pydantic State, the result is an AgentState or converted to dict/AgentState
        if isinstance(final_state_raw, dict):
            final_state = AgentState.model_validate(final_state_raw)
        else:
            final_state = final_state_raw

        # 1. Pipeline Completion
        assert final_state.is_complete is True
        assert final_state.workflow_step == "COMPLETED"

        # 2. Verify all 10 agent state contracts
        assert final_state.weather is not None
        assert final_state.weather.temperature_c is not None

        assert final_state.soil is not None
        assert final_state.soil.soil_stress_index is not None

        assert final_state.crop is not None
        assert final_state.crop.crop_coefficient_kc is not None

        assert final_state.et0 is not None
        assert final_state.et0.et0_reference_mm is not None

        assert final_state.historical is not None
        assert final_state.historical.avg_rainfall_30d_mm is not None

        assert final_state.irrigation_decision is not None
        assert final_state.irrigation_decision.decision is not None

        assert len(final_state.zone_plans) >= 1
        assert final_state.zone_plans[0].zone_id == zone.id

        assert final_state.optimization is not None
        assert final_state.optimization.baseline_volume_mm is not None

        assert final_state.risk is not None
        assert final_state.risk.overall_risk_level is not None

        assert final_state.advisory is not None
        assert len(final_state.advisory.recommended_action) > 0
        assert len(final_state.advisory.full_explanation) > 100

        # 3. Verify Execution Telemetry
        assert len(final_state.agent_executions) >= 10
        completed = [r for r in final_state.agent_executions if r.status == AgentStatus.COMPLETED]
        assert len(completed) >= 10

    def test_workflow_error_containment_on_agent_failure(self, db, initial_workflow_state):
        from app.schemas.agent_state import AgentState, AgentStatus
        from app.workflow.agent_workflow import create_agent_workflow

        state, farm, field, zone = initial_workflow_state

        with patch("app.agents.crop.crop_agent.CropAgent._run") as mock_crop:
            mock_crop.side_effect = RuntimeError("Crop agent database timeout")

            graph = create_agent_workflow(db)
            final_state_raw = graph.invoke(state)
            if isinstance(final_state_raw, dict):
                final_state = AgentState.model_validate(final_state_raw)
            else:
                final_state = final_state_raw

            # Workflow should NOT crash; it should continue through to completion
            assert final_state.is_complete is True
            assert any(r.status == AgentStatus.FAILED for r in final_state.agent_executions)
            # Downstream agents still executed
            assert final_state.advisory is not None

