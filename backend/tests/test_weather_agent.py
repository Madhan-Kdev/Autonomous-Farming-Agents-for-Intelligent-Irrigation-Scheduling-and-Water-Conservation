"""
Phase 5 — Weather Intelligence Agent tests.

All external HTTP calls are mocked.
Tests cover:
1. WeatherAgent executes and populates weather/et0 state sections.
2. Correct handling of missing farm_id.
3. Irrigation suitability logic (rain, wind, frost thresholds).
4. ET0 values are populated in state.et0.
5. Fallback to simulated data when NASA POWER is unavailable.
6. Agent failure doesn't crash workflow (BaseAgent error isolation).
7. Evidence list is populated.
8. Confidence scoring based on data source.
"""

from __future__ import annotations

import math
import os
from datetime import date, timedelta
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
def base_state(db):
    """AgentState with the demo farm_id set in request context."""
    from app.repositories.repositories import FarmRepository
    from app.schemas.agent_state import AgentState, RequestContext
    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    state = AgentState()
    state.request = RequestContext(farm_id=farm.id)
    return state, farm


@pytest.fixture
def empty_state():
    """AgentState with no request context."""
    from app.schemas.agent_state import AgentState
    return AgentState()


def _good_nasa_records(farm_id: int = 1):
    """Two days of valid simulated NASA POWER records."""
    yesterday = date.today() - timedelta(days=1)
    day_before = yesterday - timedelta(days=1)
    return [
        {
            "observation_date": day_before,
            "source": "NASA_POWER",
            "temperature_max_c": 33.0,
            "temperature_min_c": 20.0,
            "temperature_mean_c": 26.0,
            "humidity_max_pct": 72.0,
            "humidity_min_pct": 38.0,
            "humidity_mean_pct": 55.0,
            "wind_speed_m_s": 2.5,
            "solar_radiation_mj_m2": 21.5,
            "precipitation_mm": 0.0,
            "pressure_kpa": 99.2,
            "dew_point_c": None,
            "sunshine_hours": None,
            "raw_response": None,
        },
        {
            "observation_date": yesterday,
            "source": "NASA_POWER",
            "temperature_max_c": 35.0,
            "temperature_min_c": 22.0,
            "temperature_mean_c": 28.0,
            "humidity_max_pct": 65.0,
            "humidity_min_pct": 30.0,
            "humidity_mean_pct": 47.0,
            "wind_speed_m_s": 3.0,
            "solar_radiation_mj_m2": 23.0,
            "precipitation_mm": 0.0,
            "pressure_kpa": 99.0,
            "dew_point_c": None,
            "sunshine_hours": None,
            "raw_response": None,
        },
    ]


# ================================================================== #
# 1. Basic execution
# ================================================================== #

@patch("app.service.nasa_power_client.requests.get")
def test_weather_agent_executes_successfully(mock_get, db, base_state):
    """WeatherAgent.execute() must complete without raising."""
    from app.agents.weather.weather_agent import WeatherAgent
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    # Return empty structure — agent will use simulated fallback
    mock_resp.json.return_value = {
        "properties": {"parameter": {
            "T2M_MAX": {}, "T2M_MIN": {}, "T2M": {},
            "RH2M": {}, "RH2M_MAX": {}, "RH2M_MIN": {},
            "WS2M": {}, "ALLSKY_SFC_SW_DWN": {}, "PRECTOTCORR": {}, "PS": {},
        }}
    }
    mock_get.return_value = mock_resp

    state, farm = base_state
    agent = WeatherAgent(db=db, config={"use_fallback_simulation": True})
    result = agent.execute(state)

    assert result is not None
    assert result.weather is not None
    assert result.et0 is not None
    db.rollback()


@patch("app.agents.weather.weather_agent.WeatherDataService.fetch_and_store_nasa_power")
def test_weather_agent_populates_weather_context(mock_fetch, db, base_state):
    """state.weather must be populated after agent execution."""
    mock_fetch.return_value = {"stored": 0, "skipped": 0}
    from app.agents.weather.weather_agent import WeatherAgent
    state, farm = base_state
    agent = WeatherAgent(db=db, config={"use_fallback_simulation": True})
    result = agent.execute(state)
    assert result.weather is not None
    assert result.weather.data_source is not None
    db.rollback()


@patch("app.agents.weather.weather_agent.WeatherDataService.fetch_and_store_nasa_power")
def test_weather_agent_populates_et0_context(mock_fetch, db, base_state):
    """state.et0 must be populated after agent execution."""
    mock_fetch.return_value = {"stored": 0, "skipped": 0}
    from app.agents.weather.weather_agent import WeatherAgent
    state, farm = base_state
    agent = WeatherAgent(db=db, config={"use_fallback_simulation": True})
    result = agent.execute(state)
    assert result.et0 is not None
    db.rollback()


# ================================================================== #
# 2. Missing farm_id
# ================================================================== #

def test_weather_agent_handles_missing_farm_id(empty_state, db):
    """Agent must not crash when no farm_id is set — graceful degradation."""
    from app.agents.weather.weather_agent import WeatherAgent
    agent = WeatherAgent(db=db)
    result = agent.execute(empty_state)
    assert result.weather is not None
    assert result.weather.data_source == "none"
    assert len(result.warnings) >= 1


def test_weather_agent_handles_invalid_farm_id(db):
    """Agent must not crash for non-existent farm_id."""
    from app.agents.weather.weather_agent import WeatherAgent
    from app.schemas.agent_state import AgentState, RequestContext
    state = AgentState()
    state.request = RequestContext(farm_id=99999)
    agent = WeatherAgent(db=db)
    result = agent.execute(state)
    assert result.weather is not None
    assert len(result.warnings) >= 1


# ================================================================== #
# 3. Irrigation suitability logic
# ================================================================== #

@patch("app.agents.weather.weather_agent.WeatherDataService.fetch_and_store_nasa_power")
@patch("app.agents.weather.weather_agent.WeatherAgent._fetch_weather")
def test_heavy_rain_makes_irrigation_unsuitable(mock_fetch, mock_svc, db, base_state):
    """Precipitation >= 10mm must set irrigation_suitable=False."""
    mock_svc.return_value = {"stored": 0, "skipped": 0}
    mock_fetch.return_value = {
        "observation_date": date.today() - timedelta(days=1),
        "source": "NASA_POWER",
        "temperature_max_c": 28.0, "temperature_min_c": 18.0,
        "temperature_mean_c": 23.0, "humidity_mean_pct": 80.0,
        "humidity_max_pct": 90.0, "humidity_min_pct": 70.0,
        "wind_speed_m_s": 1.5, "solar_radiation_mj_m2": 15.0,
        "precipitation_mm": 25.0,  # <-- heavy rain
        "pressure_kpa": 101.0,
    }
    from app.agents.weather.weather_agent import WeatherAgent
    state, farm = base_state
    agent = WeatherAgent(db=db, config={"use_fallback_simulation": False})
    result = agent.execute(state)
    assert result.weather.irrigation_suitable is False
    assert result.weather.weather_risk_level in ("HIGH", "MEDIUM")
    db.rollback()


@patch("app.agents.weather.weather_agent.WeatherAgent._fetch_weather")
def test_no_rain_makes_irrigation_suitable(mock_fetch, db, base_state):
    """No rain + normal conditions must set irrigation_suitable=True."""
    mock_fetch.return_value = {
        "observation_date": date.today() - timedelta(days=1),
        "source": "simulated",
        "temperature_max_c": 32.0, "temperature_min_c": 20.0,
        "temperature_mean_c": 26.0, "humidity_mean_pct": 50.0,
        "humidity_max_pct": 65.0, "humidity_min_pct": 35.0,
        "wind_speed_m_s": 2.0, "solar_radiation_mj_m2": 22.0,
        "precipitation_mm": 0.0,
        "pressure_kpa": 101.0,
    }
    from app.agents.weather.weather_agent import WeatherAgent
    state, farm = base_state
    agent = WeatherAgent(db=db, config={"use_fallback_simulation": False})
    result = agent.execute(state)
    assert result.weather.irrigation_suitable is True
    db.rollback()


@patch("app.agents.weather.weather_agent.WeatherAgent._fetch_weather")
def test_very_high_wind_makes_irrigation_unsuitable(mock_fetch, db, base_state):
    """Wind >= 8 m/s must set irrigation_suitable=False."""
    mock_fetch.return_value = {
        "observation_date": date.today() - timedelta(days=1),
        "source": "simulated",
        "temperature_max_c": 30.0, "temperature_min_c": 18.0,
        "temperature_mean_c": 24.0, "humidity_mean_pct": 45.0,
        "humidity_max_pct": 60.0, "humidity_min_pct": 30.0,
        "wind_speed_m_s": 10.0,  # <-- very high wind
        "solar_radiation_mj_m2": 20.0,
        "precipitation_mm": 0.0, "pressure_kpa": 101.0,
    }
    from app.agents.weather.weather_agent import WeatherAgent
    state, farm = base_state
    agent = WeatherAgent(db=db)
    result = agent.execute(state)
    assert result.weather.irrigation_suitable is False
    db.rollback()


@patch("app.agents.weather.weather_agent.WeatherAgent._fetch_weather")
def test_frost_temp_makes_irrigation_unsuitable(mock_fetch, db, base_state):
    """Temperature <= 2°C must trigger frost risk and set unsuitable."""
    mock_fetch.return_value = {
        "observation_date": date.today() - timedelta(days=1),
        "source": "simulated",
        "temperature_max_c": 4.0, "temperature_min_c": 0.0,
        "temperature_mean_c": 1.5,  # <-- frost risk
        "humidity_mean_pct": 85.0,
        "humidity_max_pct": 92.0, "humidity_min_pct": 78.0,
        "wind_speed_m_s": 1.0, "solar_radiation_mj_m2": 8.0,
        "precipitation_mm": 0.0, "pressure_kpa": 101.0,
    }
    from app.agents.weather.weather_agent import WeatherAgent
    state, farm = base_state
    agent = WeatherAgent(db=db)
    result = agent.execute(state)
    assert result.weather.irrigation_suitable is False
    assert "frost" in result.weather.weather_summary.lower() or \
           any("frost" in e.lower() for e in result.weather.evidence)
    db.rollback()


# ================================================================== #
# 4. ET0 in state
# ================================================================== #

@patch("app.agents.weather.weather_agent.WeatherAgent._fetch_weather")
def test_et0_is_positive_for_valid_inputs(mock_fetch, db, base_state):
    """ET0 must be a positive float for valid inputs."""
    mock_fetch.return_value = {
        "observation_date": date.today() - timedelta(days=1),
        "source": "NASA_POWER",
        "temperature_max_c": 34.0, "temperature_min_c": 21.0,
        "temperature_mean_c": 27.5, "humidity_mean_pct": 50.0,
        "humidity_max_pct": 68.0, "humidity_min_pct": 32.0,
        "wind_speed_m_s": 2.5, "solar_radiation_mj_m2": 22.0,
        "precipitation_mm": 0.0, "pressure_kpa": 99.0,
    }
    from app.agents.weather.weather_agent import WeatherAgent
    state, farm = base_state
    agent = WeatherAgent(db=db)
    result = agent.execute(state)
    assert result.et0.et0_reference_mm is not None
    assert result.et0.et0_reference_mm > 0
    db.rollback()


@patch("app.agents.weather.weather_agent.WeatherAgent._fetch_weather")
def test_et0_method_is_fao56_pm(mock_fetch, db, base_state):
    """ET0 calculation method must be 'FAO56_PM'."""
    mock_fetch.return_value = {
        "observation_date": date.today() - timedelta(days=1),
        "source": "simulated",
        "temperature_max_c": 30.0, "temperature_min_c": 18.0,
        "temperature_mean_c": 24.0, "humidity_mean_pct": 55.0,
        "humidity_max_pct": 70.0, "humidity_min_pct": 40.0,
        "wind_speed_m_s": 2.0, "solar_radiation_mj_m2": 20.0,
        "precipitation_mm": 0.0, "pressure_kpa": 101.0,
    }
    from app.agents.weather.weather_agent import WeatherAgent
    state, farm = base_state
    agent = WeatherAgent(db=db)
    result = agent.execute(state)
    assert result.et0.calculation_method == "FAO56_PM"
    db.rollback()


# ================================================================== #
# 5. Confidence and evidence
# ================================================================== #

@patch("app.agents.weather.weather_agent.WeatherAgent._fetch_weather")
def test_simulated_data_has_lower_confidence(mock_fetch, db, base_state):
    """Simulated data source must result in lower confidence than real API."""
    mock_fetch.return_value = {
        "observation_date": date.today() - timedelta(days=1),
        "source": "simulated",
        "temperature_max_c": 28.0, "temperature_min_c": 16.0,
        "temperature_mean_c": 22.0, "humidity_mean_pct": 60.0,
        "humidity_max_pct": 75.0, "humidity_min_pct": 45.0,
        "wind_speed_m_s": 2.0, "solar_radiation_mj_m2": 18.0,
        "precipitation_mm": 0.0, "pressure_kpa": 101.0,
    }
    from app.agents.weather.weather_agent import WeatherAgent
    state, farm = base_state
    agent = WeatherAgent(db=db)
    result = agent.execute(state)
    assert result.weather.confidence < 0.85  # simulated = 0.60
    db.rollback()


@patch("app.agents.weather.weather_agent.WeatherAgent._fetch_weather")
def test_evidence_list_is_populated(mock_fetch, db, base_state):
    """Evidence list must contain at least one entry."""
    mock_fetch.return_value = {
        "observation_date": date.today() - timedelta(days=1),
        "source": "NASA_POWER",
        "temperature_max_c": 33.0, "temperature_min_c": 21.0,
        "temperature_mean_c": 27.0, "humidity_mean_pct": 50.0,
        "humidity_max_pct": 68.0, "humidity_min_pct": 32.0,
        "wind_speed_m_s": 2.5, "solar_radiation_mj_m2": 22.0,
        "precipitation_mm": 0.0, "pressure_kpa": 99.0,
    }
    from app.agents.weather.weather_agent import WeatherAgent
    state, farm = base_state
    agent = WeatherAgent(db=db)
    result = agent.execute(state)
    assert len(result.weather.evidence) >= 1
    assert len(result.et0.evidence) >= 1
    db.rollback()


# ================================================================== #
# 6. Agent execution record
# ================================================================== #

@patch("app.agents.weather.weather_agent.WeatherAgent._fetch_weather")
def test_execution_record_appended_to_state(mock_fetch, db, base_state):
    """A completed AgentExecutionRecord must be appended to state."""
    mock_fetch.return_value = {
        "observation_date": date.today() - timedelta(days=1),
        "source": "simulated",
        "temperature_max_c": 30.0, "temperature_min_c": 18.0,
        "temperature_mean_c": 24.0, "humidity_mean_pct": 55.0,
        "humidity_max_pct": 70.0, "humidity_min_pct": 40.0,
        "wind_speed_m_s": 2.0, "solar_radiation_mj_m2": 20.0,
        "precipitation_mm": 0.0, "pressure_kpa": 101.0,
    }
    from app.agents.weather.weather_agent import WeatherAgent
    from app.schemas.agent_state import AgentStatus
    state, farm = base_state
    agent = WeatherAgent(db=db)
    result = agent.execute(state)
    weather_records = [
        r for r in result.agent_executions
        if "weather" in r.agent_name.lower()
    ]
    assert len(weather_records) >= 1
    assert weather_records[-1].status == AgentStatus.COMPLETED
    db.rollback()


@patch("app.agents.weather.weather_agent.WeatherAgent._run")
def test_agent_exception_does_not_crash_workflow(mock_run, db, base_state):
    """Even if _run raises, execute() must return a valid state."""
    mock_run.side_effect = RuntimeError("Simulated crash")
    from app.agents.weather.weather_agent import WeatherAgent
    from app.schemas.agent_state import AgentStatus
    state, farm = base_state
    agent = WeatherAgent(db=db)
    result = agent.execute(state)
    # State is returned, not raised
    assert result is not None
    # At least one execution record with FAILED status
    failed = [r for r in result.agent_executions if r.status == AgentStatus.FAILED]
    assert len(failed) >= 1
    db.rollback()
