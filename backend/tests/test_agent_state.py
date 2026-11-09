"""
Tests for the AgentState schema and all sub-models.

Tests:
- AgentState can be instantiated with defaults.
- All sub-model sections are present.
- Enumerations have expected values.
- State serialises to JSON correctly.
- Confidence fields are bounded [0, 1].
- run_id is a valid UUID.
- Zone plans can be added to the state.
"""

from __future__ import annotations

import json
from uuid import UUID

import pytest


def test_agent_state_default_instantiation():
    """AgentState must instantiate with all defaults without raising."""
    from app.schemas.agent_state import AgentState
    state = AgentState()
    assert state is not None


def test_agent_state_has_run_id():
    """AgentState must have a UUID run_id."""
    from app.schemas.agent_state import AgentState
    state = AgentState()
    assert isinstance(state.run_id, UUID)


def test_agent_state_run_ids_are_unique():
    """Two separate AgentState instances must have different run_ids."""
    from app.schemas.agent_state import AgentState
    s1 = AgentState()
    s2 = AgentState()
    assert s1.run_id != s2.run_id


def test_agent_state_sections_exist():
    """AgentState must have all required section attributes."""
    from app.schemas.agent_state import AgentState
    state = AgentState()
    sections = [
        "request", "weather", "soil", "crop", "et0",
        "historical", "zone_plans", "irrigation_decision",
        "optimization", "risk", "advisory",
        "agent_executions", "errors", "warnings",
    ]
    for section in sections:
        assert hasattr(state, section), f"Missing section: {section}"


def test_agent_state_errors_is_list():
    """errors field must default to an empty list."""
    from app.schemas.agent_state import AgentState
    state = AgentState()
    assert isinstance(state.errors, list)
    assert len(state.errors) == 0


def test_agent_state_zone_plans_is_list():
    """zone_plans must default to an empty list."""
    from app.schemas.agent_state import AgentState
    state = AgentState()
    assert isinstance(state.zone_plans, list)


def test_zone_plan_can_be_added():
    """A ZoneIrrigationPlan can be appended to AgentState.zone_plans."""
    from app.schemas.agent_state import AgentState, IrrigationPriority, ZoneIrrigationPlan
    state = AgentState()
    plan = ZoneIrrigationPlan(
        zone_id=1,
        zone_name="Zone A",
        irrigation_required=True,
        recommended_volume_mm=12.5,
        priority=IrrigationPriority.HIGH,
        confidence=0.85,
    )
    state.zone_plans.append(plan)
    assert len(state.zone_plans) == 1
    assert state.zone_plans[0].zone_id == 1


def test_irrigation_decision_enum_values():
    """IrrigationDecision enum must have expected members."""
    from app.schemas.agent_state import IrrigationDecision
    assert IrrigationDecision.REQUIRED == "REQUIRED"
    assert IrrigationDecision.POSTPONED == "POSTPONED"
    assert IrrigationDecision.NOT_REQUIRED == "NOT_REQUIRED"
    assert IrrigationDecision.INSUFFICIENT_DATA == "INSUFFICIENT_DATA"


def test_risk_severity_enum_values():
    """RiskSeverity enum must have expected members."""
    from app.schemas.agent_state import RiskSeverity
    assert RiskSeverity.CRITICAL == "CRITICAL"
    assert RiskSeverity.HIGH == "HIGH"
    assert RiskSeverity.MEDIUM == "MEDIUM"
    assert RiskSeverity.LOW == "LOW"
    assert RiskSeverity.INFO == "INFO"


def test_agent_status_enum_values():
    """AgentStatus enum must have expected members."""
    from app.schemas.agent_state import AgentStatus
    assert AgentStatus.PENDING == "PENDING"
    assert AgentStatus.RUNNING == "RUNNING"
    assert AgentStatus.COMPLETED == "COMPLETED"
    assert AgentStatus.FAILED == "FAILED"


def test_weather_context_confidence_bounds():
    """WeatherContext confidence must be bounded [0.0, 1.0]."""
    from pydantic import ValidationError
    from app.schemas.agent_state import WeatherContext
    with pytest.raises(ValidationError):
        WeatherContext(confidence=1.5)
    with pytest.raises(ValidationError):
        WeatherContext(confidence=-0.1)


def test_agent_state_serialises_to_json():
    """AgentState must serialise to valid JSON without error."""
    from app.schemas.agent_state import AgentState
    state = AgentState()
    json_str = state.model_dump_json()
    parsed = json.loads(json_str)
    assert "run_id" in parsed
    assert "request" in parsed


def test_risk_item_requires_type_and_severity():
    """RiskItem must require risk_type and severity."""
    from app.schemas.agent_state import RiskItem, RiskSeverity
    item = RiskItem(
        risk_type="HighTemperature",
        severity=RiskSeverity.HIGH,
        description="Temperature exceeds 40°C.",
    )
    assert item.risk_type == "HighTemperature"
    assert item.severity == RiskSeverity.HIGH


def test_agent_execution_record_defaults():
    """AgentExecutionRecord must default to PENDING status."""
    from app.schemas.agent_state import AgentExecutionRecord, AgentStatus
    record = AgentExecutionRecord(agent_name="TestAgent")
    assert record.status == AgentStatus.PENDING
    assert record.started_at is None
    assert record.duration_ms is None

