"""
Phase 9 — Historical Intelligence Agent tests.

Tests cover:
1. Historical water analytics calculations: 30-day rainfall, 7-day irrigation, volume in Liters.
2. Anomaly detection: over-irrigation and under-irrigation identification.
3. Seasonal agro-climatic demand classification across annual calendar months.
4. HistoricalAgent execution, state updates, evidence generation, and BaseAgent error containment.
"""

from __future__ import annotations

import os
from datetime import date
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
def demo_historical_state(db):
    """AgentState with demo farm and Zone-1 context."""
    from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
    from app.schemas.agent_state import (
        AgentState,
        CropContext,
        ET0Context,
        RequestContext,
        SoilContext,
        WeatherContext,
    )

    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zone = ZoneRepository(db).get_active_zones(field.id)[0]  # Zone-1 (2.0 ha)

    state = AgentState()
    state.request = RequestContext(farm_id=farm.id, field_id=field.id, zone_ids=[zone.id])
    state.weather = WeatherContext(temperature_c=30.0, rainfall_mm=0.0)
    state.soil = SoilContext(soil_stress_index=0.1)
    state.crop = CropContext(crop_type="Wheat", crop_water_requirement_mm=4.5)
    state.et0 = ET0Context(et0_reference_mm=5.0, etc_mm=4.5)
    return state, zone


# ================================================================== #
# 1. Historical Analytics Unit Tests
# ================================================================== #

class TestHistoricalAnalytics:

    def test_rainfall_30d_statistics(self):
        from app.service.historical_analytics import compute_historical_water_metrics

        # 30 days of rain, 5 rain days totaling 25 mm
        rains = [0.0] * 25 + [5.0, 5.0, 5.0, 5.0, 5.0]
        metrics = compute_historical_water_metrics(
            rainfall_records=rains,
            irrigation_records_7d=[0.0] * 7,
            zone_area_ha=1.0,
            cumulative_etc_7d=28.0,
        )
        assert metrics.total_rainfall_30d_mm == pytest.approx(25.0, abs=0.1)
        assert metrics.avg_rainfall_30d_mm == pytest.approx(25.0 / 30.0, abs=0.05)
        assert metrics.rain_days_30d == 5

    def test_irrigation_liters_conversion(self):
        from app.service.historical_analytics import compute_historical_water_metrics

        # 20 mm applied over 2.5 hectares
        # 1 mm * 1 ha * 10,000 = 10,000 Liters
        # 20 mm * 2.5 ha * 10,000 = 500,000 Liters
        metrics = compute_historical_water_metrics(
            rainfall_records=[0.0] * 30,
            irrigation_records_7d=[10.0, 0.0, 10.0, 0.0, 0.0, 0.0, 0.0],
            zone_area_ha=2.5,
            cumulative_etc_7d=25.0,
        )
        assert metrics.total_irrigation_7d_mm == pytest.approx(20.0, abs=0.1)
        assert metrics.water_usage_7d_liters == pytest.approx(500000.0, abs=1.0)

    def test_over_irrigation_detection(self):
        from app.service.historical_analytics import compute_historical_water_metrics

        # 7d Demand is 20mm ETc. Supply applied is 35mm irrigation + 5mm rain = 40mm
        # 40 / 20 = 2.0 > 1.40 threshold -> Over-irrigation
        metrics = compute_historical_water_metrics(
            rainfall_records=[0.0] * 23 + [5.0] * 7,
            irrigation_records_7d=[5.0] * 7,  # 35mm
            zone_area_ha=1.0,
            cumulative_etc_7d=20.0,
        )
        assert metrics.detected_over_irrigation is True
        assert metrics.detected_under_irrigation is False

    def test_under_irrigation_detection(self):
        from app.service.historical_analytics import compute_historical_water_metrics

        # 7d Demand is 35mm ETc. Supply applied is 10mm (0.28 ratio < 0.60) AND soil stress = 0.5
        metrics = compute_historical_water_metrics(
            rainfall_records=[0.0] * 30,
            irrigation_records_7d=[10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            zone_area_ha=1.0,
            cumulative_etc_7d=35.0,
            recent_soil_stress_index=0.5,
        )
        assert metrics.detected_under_irrigation is True
        assert metrics.detected_over_irrigation is False

    def test_seasonal_pattern_classification(self):
        from app.service.historical_analytics import compute_historical_water_metrics

        summer_metrics = compute_historical_water_metrics(
            rainfall_records=[0.0],
            irrigation_records_7d=[0.0],
            target_date=date(2026, 4, 15),
        )
        assert summer_metrics.seasonal_demand_pattern == "PRE_MONSOON_SUMMER_PEAK"

        monsoon_metrics = compute_historical_water_metrics(
            rainfall_records=[0.0],
            irrigation_records_7d=[0.0],
            target_date=date(2026, 7, 20),
        )
        assert monsoon_metrics.seasonal_demand_pattern == "MONSOON_WET_SEASON"


# ================================================================== #
# 2. Historical Agent Execution Tests
# ================================================================== #

class TestHistoricalAgentExecution:

    def test_historical_agent_executes_successfully(self, db, demo_historical_state):
        from app.agents.historical.historical_agent import HistoricalAgent

        state, zone = demo_historical_state
        agent = HistoricalAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        assert result.historical is not None
        assert result.historical.avg_rainfall_30d_mm is not None
        assert result.historical.avg_irrigation_7d_mm is not None
        assert result.historical.historical_water_usage_l is not None
        assert result.historical.confidence >= 0.65
        assert len(result.historical.evidence) >= 4
        assert "Liters" in result.historical.historical_summary

    def test_historical_agent_water_volume_scales_with_area(self, db, demo_historical_state):
        from app.agents.historical.historical_agent import HistoricalAgent

        state, zone = demo_historical_state
        agent = HistoricalAgent(db=db)
        result = agent.execute(state)

        # Zone-1 has 2.0 hectares: 1mm over 1ha is 10,000L
        hist = result.historical
        expected_liters = hist.avg_irrigation_7d_mm * 7.0 * zone.area_ha * 10000.0
        assert hist.historical_water_usage_l == pytest.approx(expected_liters, rel=1e-2)

    def test_historical_agent_missing_request_handled_gracefully(self, db):
        from app.agents.historical.historical_agent import HistoricalAgent
        from app.schemas.agent_state import AgentState

        agent = HistoricalAgent(db=db)
        state = AgentState()
        result = agent.execute(state)

        assert result.historical is not None
        assert len(result.warnings) >= 1

    def test_historical_agent_execution_record_logged(self, db, demo_historical_state):
        from app.agents.historical.historical_agent import HistoricalAgent
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_historical_state
        agent = HistoricalAgent(db=db)
        result = agent.execute(state)

        hist_records = [
            r for r in result.agent_executions
            if "historical" in r.agent_name.lower()
        ]
        assert len(hist_records) >= 1
        assert hist_records[-1].status == AgentStatus.COMPLETED

    @patch("app.agents.historical.historical_agent.HistoricalAgent._run")
    def test_historical_agent_exception_contained(self, mock_run, db, demo_historical_state):
        mock_run.side_effect = RuntimeError("Historical database connection interrupted")
        from app.agents.historical.historical_agent import HistoricalAgent
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_historical_state
        agent = HistoricalAgent(db=db)
        result = agent.execute(state)

        assert result is not None
        failed = [r for r in result.agent_executions if r.status == AgentStatus.FAILED]
        assert len(failed) >= 1
