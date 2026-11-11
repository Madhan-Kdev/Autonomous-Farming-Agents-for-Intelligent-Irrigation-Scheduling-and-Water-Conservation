"""
Unit and Integration Tests for Gymnasium Agricultural Environment,
PPO Policy Inference, and /api/v1/rl/benchmark Endpoint.
"""

from __future__ import annotations

import os
import pytest
import numpy as np
from fastapi.testclient import TestClient

from app.service.rl_environment import IrrigationGymEnv, DISCRETE_ACTIONS
from app.service.ppo_policy import PPOPolicyInference

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://postgres:FarmAgent2024!@localhost:5432/autonomous_farming"
)
os.environ["DEBUG"] = "false"


@pytest.fixture(scope="module")
def client():
    from app.core.config import _reset_settings
    _reset_settings()
    from app.main import app
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. Gymnasium Environment Tests
# ---------------------------------------------------------------------------


class TestGymnasiumEnvironment:
    """Validate Gymnasium environment compliance and physics."""

    def test_env_instantiation_discrete(self):
        env = IrrigationGymEnv(continuous_actions=False)
        assert env.action_space.n == 5
        assert env.observation_space.shape == (9,)

    def test_env_instantiation_continuous(self):
        env = IrrigationGymEnv(continuous_actions=True)
        assert env.action_space.shape == (1,)
        assert env.action_space.low[0] == 0.0
        assert env.action_space.high[0] == 30.0

    def test_env_reset(self):
        env = IrrigationGymEnv()
        obs, info = env.reset(seed=42)
        assert isinstance(obs, np.ndarray)
        assert obs.shape == (9,)
        assert "step" in info
        assert info["step"] == 0

    def test_env_step_discrete(self):
        env = IrrigationGymEnv(continuous_actions=False)
        env.reset(seed=10, options={"soil_moisture_pct": 15.0, "field_capacity_pct": 30.0, "wilting_point_pct": 12.0})
        # Action 2 is 10mm
        obs, reward, terminated, truncated, info = env.step(2)
        assert obs.shape == (9,)
        assert isinstance(reward, float)
        assert not terminated
        assert info["action_applied_mm"] == 10.0
        assert "reward_breakdown" in info

    def test_env_rain_penalty(self):
        """Irrigating during heavy forecast rain should incur rain waste penalty."""
        env = IrrigationGymEnv()
        env.reset(options={"forecast_rain_mm": 20.0, "soil_moisture_pct": 25.0})
        # Apply 15mm irrigation during heavy rain
        _, _, _, _, info = env.step(3)
        breakdown = info["reward_breakdown"]
        assert breakdown["rain_waste_penalty"] < 0.0

    def test_env_deep_percolation(self):
        """Applying huge irrigation to saturated soil should cause deep percolation."""
        env = IrrigationGymEnv()
        env.reset(options={"soil_moisture_pct": 29.5, "field_capacity_pct": 30.0})
        # Action 4 is 25mm -> should exceed FC and drain
        _, _, _, _, info = env.step(4)
        assert info["deep_percolation_mm"] > 0.0
        assert info["reward_breakdown"]["percolation_penalty"] < 0.0


# ---------------------------------------------------------------------------
# 2. PPO Policy Inference Tests
# ---------------------------------------------------------------------------


class TestPPOPolicyInference:
    """Validate policy decision logic and action probability distribution."""

    def test_ppo_high_rain_selects_zero_irrigation(self):
        policy = PPOPolicyInference()
        res = policy.evaluate_state(
            soil_moisture_pct=20.0,
            field_capacity_pct=30.0,
            wilting_point_pct=12.0,
            et0_mm=5.0,
            etc_mm=5.5,
            forecast_rain_mm=25.0,
            temperature_c=25.0,
        )
        assert res.action_mm == 0.0
        assert res.action_probabilities["0mm"] > 0.70

    def test_ppo_drought_selects_refill(self):
        policy = PPOPolicyInference()
        res = policy.evaluate_state(
            soil_moisture_pct=11.0,  # below WP (12.0)
            field_capacity_pct=30.0,
            wilting_point_pct=12.0,
            et0_mm=6.5,
            etc_mm=7.2,
            forecast_rain_mm=0.0,
            temperature_c=36.0,
        )
        assert res.action_mm >= 15.0
        assert res.crop_stress_anticipated < 1.0

    def test_ppo_optimal_soil_conserves_water(self):
        policy = PPOPolicyInference()
        res = policy.evaluate_state(
            soil_moisture_pct=28.0,  # very close to FC (30.0)
            field_capacity_pct=30.0,
            wilting_point_pct=12.0,
            et0_mm=4.0,
            etc_mm=4.2,
            forecast_rain_mm=0.0,
            temperature_c=24.0,
        )
        assert res.action_mm == 0.0


# ---------------------------------------------------------------------------
# 3. Benchmark API Endpoint Tests
# ---------------------------------------------------------------------------


class TestRLBenchmarkEndpoint:
    """Validate POST /api/v1/rl/benchmark."""

    def test_benchmark_normal_scenario(self, client: TestClient):
        payload = {
            "soil_moisture_pct": 18.0,
            "field_capacity_pct": 30.0,
            "wilting_point_pct": 12.0,
            "et0_mm": 5.0,
            "etc_mm": 5.5,
            "forecast_rain_mm": 0.0,
            "temperature_c": 28.0,
            "growth_stage": "mid",
            "crop_name": "Wheat",
        }
        resp = client.post("/api/v1/rl/benchmark", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        data = body["data"]

        assert "rule_decision" in data
        assert "ppo_policy" in data
        assert "volume_delta_mm" in data
        assert "water_savings_vs_rule_pct" in data
        assert "alignment" in data
        assert "synthesis" in data

        assert data["rule_decision"]["recommended_volume_mm"] >= 0.0
        assert data["ppo_policy"]["action_mm"] in DISCRETE_ACTIONS
        assert len(data["ppo_policy"]["action_probabilities"]) == 5

    def test_benchmark_rainy_scenario_agreement(self, client: TestClient):
        payload = {
            "soil_moisture_pct": 20.0,
            "field_capacity_pct": 30.0,
            "wilting_point_pct": 12.0,
            "et0_mm": 4.0,
            "etc_mm": 4.2,
            "forecast_rain_mm": 18.0,  # Rain conflict!
            "temperature_c": 24.0,
        }
        resp = client.post("/api/v1/rl/benchmark", json=payload)
        assert resp.status_code == 200
        data = resp.json()["data"]

        # Both engines should avoid irrigation
        assert data["rule_decision"]["decision"] in ("POSTPONED", "NOT_REQUIRED")
        assert data["ppo_policy"]["action_mm"] == 0.0
        assert data["alignment"] in ("AGREE", "RAIN_HARVEST")

    def test_benchmark_invalid_soil_bounds_422(self, client: TestClient):
        payload = {
            "soil_moisture_pct": 20.0,
            "field_capacity_pct": 12.0,
            "wilting_point_pct": 18.0,  # FC < WP is invalid
        }
        resp = client.post("/api/v1/rl/benchmark", json=payload)
        assert resp.status_code == 422
