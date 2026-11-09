"""
Phase 13 — Risk and Anomaly Agent tests.

Tests cover:
1. Frost risk detection (temperature <= 2.0°C).
2. Heatwave risk detection (temperature >= 38.0°C).
3. Rain conflict detection (irrigation scheduled during significant rainfall).
4. High wind drift hazard (wind >= 8.0 m/s).
5. Soil saturation / waterlogging hazard.
6. Severe drought stress / desiccation risk.
7. Sensor anomalies (out-of-bound readings, inverted thresholds).
8. Hydraulic overload prevention (scheduled volume exceeds zone intake ceiling).
9. Safe nominal baseline (no false alarms when all parameters nominal).
10. RiskAnomalyAgent execution, state population (state.risk), and BaseAgent error containment.
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
def demo_nominal_state(db):
    """AgentState with all parameters nominal and safe."""
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
        WeatherContext,
    )

    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zone = ZoneRepository(db).get_active_zones(field.id)[0]

    state = AgentState()
    state.request = RequestContext(farm_id=farm.id, field_id=field.id, zone_ids=[zone.id])
    state.weather = WeatherContext(
        temperature_c=24.0,
        wind_speed_ms=3.2,
        rainfall_mm=0.0,
        forecast_rainfall_7d_mm=2.0,
        irrigation_suitable=True,
    )
    state.soil = SoilContext(
        zone_id=zone.id,
        soil_moisture_pct=25.0,
        field_capacity_pct=30.0,
        wilting_point_pct=14.0,
        available_water_pct=68.0,
        soil_stress_index=0.15,
        is_over_wet=False,
        is_over_dry=False,
    )
    state.irrigation_decision = IrrigationDecisionContext(
        decision=IrrigationDecision.REQUIRED,
        priority=IrrigationPriority.MEDIUM,
        recommended_volume_mm=12.0,
        affected_zones=[zone.id],
    )
    return state, zone


# ================================================================== #
# 1. Unit Tests for Risk Diagnostic Engine
# ================================================================== #

class TestRiskEngine:
    def test_nominal_conditions_produce_no_severe_risks(self):
        from app.schemas.agent_state import RiskSeverity
        from app.service.risk_engine import evaluate_system_risks

        result = evaluate_system_risks(
            temperature_c=22.0,
            wind_speed_ms=2.5,
            rainfall_mm=0.0,
            forecast_rain_7d_mm=0.0,
            soil_moisture_pct=26.0,
            field_capacity_pct=32.0,
            wilting_point_pct=14.0,
            available_water_pct=65.0,
            soil_stress_index=0.10,
            is_over_wet=False,
            is_over_dry=False,
            irrigation_required=True,
            recommended_volume_mm=12.0,
            max_irrigation_capacity_mm=35.0,
        )
        assert len(result.risks) == 0
        assert result.overall_risk_level == RiskSeverity.INFO
        assert result.recommendation_safe is True
        assert "nominal" in result.risk_summary.lower()

    def test_frost_hazard_detection(self):
        from app.schemas.agent_state import RiskSeverity
        from app.service.risk_engine import evaluate_system_risks

        # Near zero -> HIGH
        res1 = evaluate_system_risks(temperature_c=1.5)
        frost_risks = [r for r in res1.risks if r.risk_type == "FROST_RISK"]
        assert len(frost_risks) == 1
        assert frost_risks[0].severity == RiskSeverity.HIGH
        assert res1.recommendation_safe is False

        # Sub-zero -> CRITICAL
        res2 = evaluate_system_risks(temperature_c=-2.0)
        crit_frost = [r for r in res2.risks if r.risk_type == "FROST_RISK"]
        assert len(crit_frost) == 1
        assert crit_frost[0].severity == RiskSeverity.CRITICAL

    def test_heatwave_hazard_detection(self):
        from app.schemas.agent_state import RiskSeverity
        from app.service.risk_engine import evaluate_system_risks

        res = evaluate_system_risks(temperature_c=41.0)
        heat_risks = [r for r in res.risks if r.risk_type == "HEATWAVE_RISK"]
        assert len(heat_risks) == 1
        assert heat_risks[0].severity == RiskSeverity.HIGH
        assert any("thermal stress" in ev.lower() for ev in heat_risks[0].evidence)

    def test_rain_conflict_hazard(self):
        from app.schemas.agent_state import RiskSeverity
        from app.service.risk_engine import evaluate_system_risks

        res = evaluate_system_risks(
            rainfall_mm=12.0,
            irrigation_required=True,
            recommended_volume_mm=20.0,
        )
        conflict = [r for r in res.risks if r.risk_type == "RAIN_CONFLICT"]
        assert len(conflict) == 1
        assert conflict[0].severity == RiskSeverity.HIGH
        assert res.recommendation_safe is False

    def test_high_wind_drift_hazard(self):
        from app.schemas.agent_state import RiskSeverity
        from app.service.risk_engine import evaluate_system_risks

        res = evaluate_system_risks(wind_speed_ms=13.5)
        wind_risks = [r for r in res.risks if r.risk_type == "HIGH_WIND_HAZARD"]
        assert len(wind_risks) == 1
        assert wind_risks[0].severity == RiskSeverity.CRITICAL
        assert "drift" in wind_risks[0].evidence[1].lower()

    def test_soil_waterlogging_hazard(self):
        from app.schemas.agent_state import RiskSeverity
        from app.service.risk_engine import evaluate_system_risks

        res = evaluate_system_risks(
            soil_moisture_pct=40.0,
            field_capacity_pct=30.0,
            is_over_wet=True,
            irrigation_required=True,
        )
        wet = [r for r in res.risks if r.risk_type == "WATERLOGGING_RISK"]
        assert len(wet) == 1
        assert wet[0].severity == RiskSeverity.HIGH

    def test_severe_drought_desiccation_hazard(self):
        from app.schemas.agent_state import RiskSeverity
        from app.service.risk_engine import evaluate_system_risks

        res = evaluate_system_risks(
            available_water_pct=8.0,
            soil_stress_index=0.90,
            is_over_dry=True,
        )
        drought = [r for r in res.risks if r.risk_type == "DROUGHT_STRESS_RISK"]
        assert len(drought) == 1
        assert drought[0].severity == RiskSeverity.CRITICAL

    def test_sensor_telemetry_out_of_bounds_anomaly(self):
        from app.schemas.agent_state import RiskSeverity
        from app.service.risk_engine import evaluate_system_risks

        # Negative reading or > 100%
        res = evaluate_system_risks(soil_moisture_pct=-5.0)
        anomaly = [r for r in res.risks if r.risk_type == "SENSOR_ANOMALY"]
        assert len(anomaly) == 1
        assert anomaly[0].severity == RiskSeverity.HIGH

    def test_hydraulic_overload_hazard(self):
        from app.schemas.agent_state import RiskSeverity
        from app.service.risk_engine import evaluate_system_risks

        res = evaluate_system_risks(
            irrigation_required=True,
            recommended_volume_mm=55.0,
            max_irrigation_capacity_mm=35.0,
        )
        overload = [r for r in res.risks if r.risk_type == "HYDRAULIC_OVERLOAD"]
        assert len(overload) == 1
        assert overload[0].severity == RiskSeverity.HIGH
        assert "exceeds" in overload[0].description


# ================================================================== #
# 2. Integration Tests for RiskAnomalyAgent Execution
# ================================================================== #

class TestRiskAnomalyAgentExecution:
    def test_risk_agent_executes_nominal_state(self, db, demo_nominal_state):
        from app.agents.risk.risk_agent import RiskAnomalyAgent
        from app.schemas.agent_state import RiskSeverity

        state, zone = demo_nominal_state
        agent = RiskAnomalyAgent(db=db)
        result = agent.execute(state)

        assert result.risk is not None
        assert result.risk.overall_risk_level == RiskSeverity.INFO
        assert result.risk.recommendation_safe is True
        assert len(result.risk.risks) == 0

    def test_risk_agent_detects_multiple_hazards(self, db, demo_nominal_state):
        from app.agents.risk.risk_agent import RiskAnomalyAgent
        from app.schemas.agent_state import RiskSeverity

        state, zone = demo_nominal_state
        # Inject extreme heatwave and severe drought
        state.weather.temperature_c = 42.0
        state.soil.soil_stress_index = 0.88
        state.soil.available_water_pct = 5.0
        state.soil.is_over_dry = True

        agent = RiskAnomalyAgent(db=db)
        result = agent.execute(state)

        assert result.risk is not None
        assert len(result.risk.risks) >= 2
        types = [r.risk_type for r in result.risk.risks]
        assert "HEATWAVE_RISK" in types
        assert "DROUGHT_STRESS_RISK" in types
        assert result.risk.overall_risk_level == RiskSeverity.CRITICAL
        assert result.risk.recommendation_safe is False

    def test_risk_agent_hydraulic_overload_from_zone_db(self, db, demo_nominal_state):
        from app.agents.risk.risk_agent import RiskAnomalyAgent

        state, zone = demo_nominal_state
        # Zone max_irrigation_mm is 35.0 mm; suggest 50.0 mm
        state.irrigation_decision.recommended_volume_mm = 50.0

        agent = RiskAnomalyAgent(db=db)
        result = agent.execute(state)

        overload = [r for r in result.risk.risks if r.risk_type == "HYDRAULIC_OVERLOAD"]
        assert len(overload) == 1
        assert "exceeds" in overload[0].description

    def test_risk_agent_execution_record_logged(self, db, demo_nominal_state):
        from app.agents.risk.risk_agent import RiskAnomalyAgent
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_nominal_state
        agent = RiskAnomalyAgent(db=db)
        result = agent.execute(state)

        records = [
            r for r in result.agent_executions
            if "risk" in r.agent_name.lower() or "anomaly" in r.agent_name.lower()
        ]
        assert len(records) >= 1
        assert records[-1].status == AgentStatus.COMPLETED

    @patch("app.agents.risk.risk_agent.RiskAnomalyAgent._run")
    def test_risk_agent_exception_contained(
        self, mock_run, db, demo_nominal_state
    ):
        mock_run.side_effect = RuntimeError("Telemetry evaluation exception")
        from app.agents.risk.risk_agent import RiskAnomalyAgent
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_nominal_state
        agent = RiskAnomalyAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        failed = [r for r in result.agent_executions if r.status == AgentStatus.FAILED]
        assert len(failed) >= 1
