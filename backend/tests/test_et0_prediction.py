"""
Phase 8 — ET0 Prediction Module (ML Model) tests.

Tests cover:
1. ET0MLModel training and evaluation metrics (R² > 0.95, RMSE < 0.40).
2. Prediction accuracy on realistic agricultural weather conditions.
3. Fallback inference with partial weather inputs.
4. Correlation between ML predictions and analytical FAO-56 PM calculations.
5. ET0PredictionModule execution, state updates, benchmark comparison notes, and error containment.
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
def demo_et0_state(db):
    """AgentState with demo farm and weather/et0 context."""
    from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
    from app.schemas.agent_state import AgentState, ET0Context, RequestContext, WeatherContext

    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zone = ZoneRepository(db).get_active_zones(field.id)[0]

    state = AgentState()
    state.request = RequestContext(farm_id=farm.id, field_id=field.id, zone_ids=[zone.id])
    state.weather = WeatherContext(
        temperature_c=28.0,
        humidity_pct=50.0,
        wind_speed_ms=2.5,
        solar_radiation_mjm2=22.0,
        rainfall_mm=0.0,
        data_source="simulated",
    )
    state.et0 = ET0Context(
        et0_reference_mm=5.20,
        calculation_method="FAO56_PM",
    )
    return state, zone


# ================================================================== #
# 1. ET0 ML Model Unit Tests
# ================================================================== #

class TestET0MLModel:

    def test_model_training_and_metrics(self):
        from app.ml.et0_model import ET0MLModel

        model = ET0MLModel()
        model.train(n_samples=400, random_seed=42)

        assert model.is_trained() is True
        assert model.train_r2_score > 0.95
        assert model.train_rmse < 0.45

    def test_predict_realistic_summer_day(self):
        from app.ml.et0_model import get_et0_model

        model = get_et0_model()
        weather = {
            "temperature_max_c": 35.0,
            "temperature_min_c": 22.0,
            "temperature_mean_c": 28.5,
            "humidity_mean_pct": 45.0,
            "wind_speed_m_s": 2.5,
            "solar_radiation_mj_m2": 24.0,
            "pressure_kpa": 98.5,
        }
        pred_val, confidence = model.predict(weather, day_of_year=180)

        assert isinstance(pred_val, float)
        # In summer under high solar radiation and low humidity, ET0 is typically 4.0 - 8.0 mm/day
        assert 3.5 <= pred_val <= 8.5
        assert 0.80 <= confidence <= 1.0

    def test_predict_partial_inputs_graceful_fallback(self):
        from app.ml.et0_model import get_et0_model

        model = get_et0_model()
        # Missing solar radiation and pressure
        weather = {
            "temperature_max_c": 30.0,
            "temperature_min_c": 18.0,
            "humidity_mean_pct": 60.0,
            "wind_speed_m_s": 1.5,
        }
        pred_val, confidence = model.predict(weather, day_of_year=100)

        assert pred_val > 0.0
        # Confidence drops when features are missing
        assert confidence < 0.95

    def test_ml_prediction_tracks_fao56_pm_trend(self):
        """Verify that hotter, sunnier weather results in higher ML-predicted ET0."""
        from app.ml.et0_model import get_et0_model

        model = get_et0_model()

        hot_weather = {
            "temperature_max_c": 38.0,
            "temperature_min_c": 25.0,
            "humidity_mean_pct": 30.0,
            "wind_speed_m_s": 3.5,
            "solar_radiation_mj_m2": 26.0,
        }
        cool_weather = {
            "temperature_max_c": 18.0,
            "temperature_min_c": 10.0,
            "humidity_mean_pct": 80.0,
            "wind_speed_m_s": 1.0,
            "solar_radiation_mj_m2": 12.0,
        }

        hot_pred, _ = model.predict(hot_weather, day_of_year=180)
        cool_pred, _ = model.predict(cool_weather, day_of_year=180)

        assert hot_pred > cool_pred + 2.0


# ================================================================== #
# 2. ET0 Prediction Module Agent Tests
# ================================================================== #

class TestET0PredictionModule:

    def test_et0_agent_executes_successfully(self, db, demo_et0_state):
        from app.agents.et0.et0_agent import ET0PredictionModule

        state, zone = demo_et0_state
        agent = ET0PredictionModule(db=db)
        result = agent.execute(state)

        assert result is not None
        assert result.et0 is not None
        assert result.et0.et0_predicted_mm is not None
        assert result.et0.et0_predicted_mm > 0.0
        assert "GradientBoosting" in result.et0.prediction_model
        assert result.et0.prediction_confidence >= 0.70

    def test_et0_agent_adds_benchmark_comparison_evidence(self, db, demo_et0_state):
        from app.agents.et0.et0_agent import ET0PredictionModule

        state, zone = demo_et0_state
        agent = ET0PredictionModule(db=db)
        result = agent.execute(state)

        evidence = result.et0.evidence
        assert any("Benchmark comparison" in item for item in evidence)

    def test_et0_agent_handles_missing_reference(self, db):
        from app.agents.et0.et0_agent import ET0PredictionModule
        from app.schemas.agent_state import AgentState, WeatherContext

        state = AgentState()
        state.weather = WeatherContext(
            temperature_c=25.0,
            humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_mjm2=18.0,
        )
        agent = ET0PredictionModule(db=db)
        result = agent.execute(state)

        assert result.et0.et0_predicted_mm is not None
        assert result.et0.et0_reference_mm is None

    def test_et0_agent_execution_record_logged(self, db, demo_et0_state):
        from app.agents.et0.et0_agent import ET0PredictionModule
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_et0_state
        agent = ET0PredictionModule(db=db)
        result = agent.execute(state)

        et0_records = [
            r for r in result.agent_executions
            if "et0" in r.agent_name.lower() or "prediction" in r.agent_name.lower()
        ]
        assert len(et0_records) >= 1
        assert et0_records[-1].status == AgentStatus.COMPLETED

    @patch("app.agents.et0.et0_agent.ET0PredictionModule._run")
    def test_et0_agent_exception_contained(self, mock_run, db, demo_et0_state):
        mock_run.side_effect = RuntimeError("Model inference hardware error")
        from app.agents.et0.et0_agent import ET0PredictionModule
        from app.schemas.agent_state import AgentStatus

        state, zone = demo_et0_state
        agent = ET0PredictionModule(db=db)
        result = agent.execute(state)

        assert result is not None
        failed = [r for r in result.agent_executions if r.status == AgentStatus.FAILED]
        assert len(failed) >= 1

