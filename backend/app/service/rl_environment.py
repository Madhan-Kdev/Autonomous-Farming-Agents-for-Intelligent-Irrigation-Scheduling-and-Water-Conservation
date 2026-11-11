"""
Gymnasium-compatible Agricultural Irrigation Simulation Environment.

Implements the official Gymnasium Env API for Deep Reinforcement Learning
(PPO / SAC / DQN) irrigation scheduling and water conservation.

Standards & Physics:
- State Space: 9-dimensional continuous observation vector (soil moisture,
  FC, WP, ET0, ETc, forecast rain, temperature, crop growth stage, stress index)
- Action Space:
    - Discrete: [0: No irrigation (0mm), 1: Light deficit (5mm),
                 2: Moderate (10mm), 3: Standard refill (15mm), 4: Heavy (25mm)]
    - Continuous: [0.0, 30.0] mm
- Reward Function:
    R = + 2.0 * (1.0 - stress_index)        # Crop health satisfaction
        - 0.08 * action_mm                  # Water conservation incentive
        - 0.40 * deep_percolation_mm        # Deep drainage waste penalty
        - (1.5 * action_mm if rain >= 5.0)  # Rain conflict penalty
        - (5.0 if moisture < WP else 0.0)   # Wilting disaster penalty

All state transitions strictly follow FAO-56 root-zone water balance equations.
"""

from __future__ import annotations

import logging
from typing import Any, SupportsFloat

import gymnasium as gym
from gymnasium import spaces
import numpy as np

logger = logging.getLogger(__name__)


# Discrete action mappings (mm depth)
DISCRETE_ACTIONS: list[float] = [0.0, 5.0, 10.0, 15.0, 25.0]

# Stage index mappings
STAGE_MAP: dict[str, int] = {
    "initial": 0,
    "development": 1,
    "mid": 2,
    "late": 3,
}
STAGE_NAMES: list[str] = ["initial", "development", "mid", "late"]


class IrrigationGymEnv(gym.Env):
    """
    Gymnasium agricultural irrigation scheduling environment.

    Metadata defines render modes and step parameters.
    """

    metadata = {"render_modes": ["human", "ansi"], "render_fps": 1}

    def __init__(
        self,
        continuous_actions: bool = False,
        root_depth_m: float = 0.60,
        application_efficiency: float = 0.90,
        max_steps: int = 30,
    ) -> None:
        super().__init__()
        self.continuous_actions = continuous_actions
        self.root_depth_m = root_depth_m
        self.application_efficiency = application_efficiency
        self.max_steps = max_steps

        # Action space
        if self.continuous_actions:
            self.action_space = spaces.Box(
                low=np.array([0.0], dtype=np.float32),
                high=np.array([30.0], dtype=np.float32),
                dtype=np.float32,
            )
        else:
            self.action_space = spaces.Discrete(len(DISCRETE_ACTIONS))

        # Observation space bounds (9 dimensions):
        # [0] Soil moisture %: [0.0, 100.0]
        # [1] Field Capacity %: [0.0, 100.0]
        # [2] Wilting Point %: [0.0, 100.0]
        # [3] ET0 mm: [0.0, 25.0]
        # [4] ETc mm: [0.0, 30.0]
        # [5] Forecast Rain mm: [0.0, 100.0]
        # [6] Temperature C: [-10.0, 55.0]
        # [7] Crop stage idx: [0.0, 3.0]
        # [8] Stress Index Ks: [0.0, 1.0]
        low = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -10.0, 0.0, 0.0], dtype=np.float32)
        high = np.array([100.0, 100.0, 100.0, 25.0, 30.0, 100.0, 55.0, 3.0, 1.0], dtype=np.float32)
        self.observation_space = spaces.Box(low=low, high=high, dtype=np.float32)

        # Internal environment state
        self._step_count = 0
        self._current_state = np.zeros(9, dtype=np.float32)
        self._last_reward_breakdown: dict[str, float] = {}

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset the environment to initial state."""
        super().reset(seed=seed)
        self._step_count = 0

        opts = options or {}
        # Allow caller to inject precise agricultural scenario
        sm = float(opts.get("soil_moisture_pct", self.np_random.uniform(14.0, 30.0)))
        fc = float(opts.get("field_capacity_pct", 30.0))
        wp = float(opts.get("wilting_point_pct", 12.0))
        et0 = float(opts.get("et0_mm", self.np_random.uniform(3.0, 7.5)))
        etc = float(opts.get("etc_mm", et0 * 1.05))
        rain = float(opts.get("forecast_rain_mm", 0.0 if self.np_random.random() > 0.3 else self.np_random.uniform(2.0, 20.0)))
        temp = float(opts.get("temperature_c", self.np_random.uniform(22.0, 36.0)))
        stage_idx = float(opts.get("growth_stage_idx", self.np_random.integers(0, 4)))

        # Compute initial stress index Ks
        ks = self._compute_stress_index(sm, fc, wp)

        self._current_state = np.array(
            [sm, fc, wp, et0, etc, rain, temp, stage_idx, ks],
            dtype=np.float32,
        )

        return self._current_state.copy(), {"step": 0, "stress_index": ks}

    def step(
        self, action: Any
    ) -> tuple[np.ndarray, SupportsFloat, bool, bool, dict[str, Any]]:
        """Execute one agricultural day step."""
        self._step_count += 1

        # Resolve action to depth in mm
        if self.continuous_actions:
            action_mm = float(np.clip(action[0], 0.0, 30.0))
        else:
            action_idx = int(action)
            action_idx = max(0, min(action_idx, len(DISCRETE_ACTIONS) - 1))
            action_mm = DISCRETE_ACTIONS[action_idx]

        sm, fc, wp, et0, etc, rain, temp, stage_idx, prev_ks = self._current_state

        # Effective rain (FAO-56 empirical: 80% if > 5mm, else 0)
        eff_rain = max(0.0, (rain - 5.0) * 0.8) if rain > 5.0 else 0.0

        # Net irrigation inflow
        net_irrigation = action_mm * self.application_efficiency

        # Inflow depth in moisture %: Δθ = Net / (10 * Zr)
        delta_theta_in = (net_irrigation + eff_rain) / (10.0 * self.root_depth_m)

        # Theoretical moisture before drainage
        theta_theo = sm + delta_theta_in

        # Deep percolation drainage if theta_theo > field_capacity
        if theta_theo > fc:
            deep_percolation_mm = (theta_theo - fc) * 10.0 * self.root_depth_m
            theta_after_drain = fc
        else:
            deep_percolation_mm = 0.0
            theta_after_drain = theta_theo

        # Outflow (evapotranspiration)
        delta_theta_out = etc / (10.0 * self.root_depth_m)
        new_sm = max(wp * 0.6, theta_after_drain - delta_theta_out)

        # New stress index
        new_ks = self._compute_stress_index(new_sm, fc, wp)

        # Reward components
        crop_health_reward = 2.0 * (1.0 - new_ks)
        water_cost_penalty = -0.08 * action_mm
        percolation_penalty = -0.40 * deep_percolation_mm
        rain_waste_penalty = -1.5 * action_mm if rain >= 5.0 and action_mm > 0.0 else 0.0
        wilting_disaster_penalty = -5.0 if new_sm <= wp else 0.0

        total_reward = (
            crop_health_reward
            + water_cost_penalty
            + percolation_penalty
            + rain_waste_penalty
            + wilting_disaster_penalty
        )

        self._last_reward_breakdown = {
            "crop_health_reward": round(crop_health_reward, 3),
            "water_cost_penalty": round(water_cost_penalty, 3),
            "percolation_penalty": round(percolation_penalty, 3),
            "rain_waste_penalty": round(rain_waste_penalty, 3),
            "wilting_disaster_penalty": round(wilting_disaster_penalty, 3),
            "total_reward": round(total_reward, 3),
        }

        # Update environment state for next day
        # Slight realistic meteorological stochastic drift
        new_temp = float(np.clip(temp + self.np_random.normal(0, 1.0), 10.0, 48.0))
        new_et0 = float(np.clip(et0 + self.np_random.normal(0, 0.4), 2.0, 12.0))
        new_etc = float(np.clip(new_et0 * (1.0 + (stage_idx * 0.08)), 2.0, 15.0))
        new_rain = float(
            self.np_random.exponential(1.5) if self.np_random.random() < 0.2 else 0.0
        )

        self._current_state = np.array(
            [new_sm, fc, wp, new_et0, new_etc, new_rain, new_temp, stage_idx, new_ks],
            dtype=np.float32,
        )

        terminated = self._step_count >= self.max_steps
        truncated = False

        info = {
            "action_applied_mm": action_mm,
            "soil_moisture_after_pct": round(new_sm, 2),
            "stress_index": round(new_ks, 3),
            "deep_percolation_mm": round(deep_percolation_mm, 2),
            "reward_breakdown": self._last_reward_breakdown,
            "step": self._step_count,
        }

        return self._current_state.copy(), float(total_reward), terminated, truncated, info

    def _compute_stress_index(self, sm: float, fc: float, wp: float) -> float:
        """
        Compute crop water stress index Ks in [0.0, 1.0].
        0.0 = Optimal, zero stress.
        1.0 = Severe wilting point drought stress.
        """
        taw = max(fc - wp, 1.0)
        p = 0.50  # average FAO depletion fraction
        raw = p * taw
        depletion = max(0.0, fc - sm)

        if depletion <= raw:
            return 0.0
        elif depletion >= taw:
            return 1.0
        else:
            return float(np.clip((depletion - raw) / ((1.0 - p) * taw), 0.0, 1.0))

    def render(self) -> str | None:
        """Render text summary."""
        sm, fc, wp, et0, etc, rain, temp, stage_idx, ks = self._current_state
        out = (
            f"Step {self._step_count} | Moisture: {sm:.1f}% (WP:{wp:.1f}% FC:{fc:.1f}%) | "
            f"ETc: {etc:.1f}mm | Rain: {rain:.1f}mm | Stress Ks: {ks:.2f}"
        )
        return out
