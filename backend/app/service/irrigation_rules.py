"""
Irrigation Decision Rules Engine.

Implements multi-factor agricultural decision logic:
- Weather constraints (impending rainfall, freezing temperatures, high winds)
- Soil moisture dynamics (over-wet saturation vs wilting desiccation)
- Crop growth stage sensitivity and water requirement (ETc)
- Calculation of net irrigation requirement (NIR)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.schemas.agent_state import IrrigationDecision, IrrigationPriority

logger = logging.getLogger(__name__)


@dataclass
class DecisionOutcome:
    """Consolidated outcome of the irrigation decision engine."""

    decision: IrrigationDecision
    priority: IrrigationPriority
    recommended_volume_mm: float
    recommended_time: str
    postponement_reason: str | None
    decision_factors: list[str] = field(default_factory=list)
    confidence: float = 0.90


def evaluate_irrigation_decision(
    weather_suitable: bool | None,
    precipitation_mm: float = 0.0,
    rainfall_forecast_mm: float = 0.0,
    wind_speed_ms: float = 0.0,
    temperature_c: float = 25.0,
    is_over_wet: bool = False,
    is_over_dry: bool = False,
    soil_stress_index: float = 0.0,
    available_water_pct: float | None = 60.0,
    water_holding_capacity_mm: float = 40.0,
    etc_mm: float = 4.0,
    crop_growth_stage: str = "mid",
    min_irrigation_mm: float = 5.0,
    max_irrigation_mm: float = 35.0,
) -> DecisionOutcome:
    """
    Evaluate multi-factor agronomic data to reach an irrigation decision.

    Returns
    -------
    DecisionOutcome
        Structured decision, priority, recommended volume, and explanation.
    """
    factors: list[str] = []

    # ------------------------------------------------------------------ #
    # Rule Group 1: Postponement Conditions (Safety & Weather Constraints)
    # ------------------------------------------------------------------ #

    # 1.1 Soil is saturated / waterlogged
    if is_over_wet:
        factors.append("Soil moisture exceeds field capacity (risk of anaerobic root rot).")
        return DecisionOutcome(
            decision=IrrigationDecision.POSTPONED,
            priority=IrrigationPriority.NONE,
            recommended_volume_mm=0.0,
            recommended_time="N/A",
            postponement_reason="Soil profile is saturated / over-wet (> field capacity).",
            decision_factors=factors,
            confidence=0.95,
        )

    # 1.2 Impending substantial rainfall
    if rainfall_forecast_mm >= 5.0 or precipitation_mm >= 10.0:
        rain_amt = max(rainfall_forecast_mm, precipitation_mm)
        factors.append(f"Significant precipitation expected or occurring ({rain_amt:.1f} mm).")
        return DecisionOutcome(
            decision=IrrigationDecision.POSTPONED,
            priority=IrrigationPriority.NONE,
            recommended_volume_mm=0.0,
            recommended_time="N/A",
            postponement_reason=f"Significant rainfall event ({rain_amt:.1f} mm) replenishes root zone.",
            decision_factors=factors,
            confidence=0.92,
        )

    # 1.3 High wind velocity
    if wind_speed_ms >= 8.0:
        factors.append(f"Wind speed ({wind_speed_ms:.1f} m/s) causes excessive spray drift.")
        return DecisionOutcome(
            decision=IrrigationDecision.POSTPONED,
            priority=IrrigationPriority.NONE,
            recommended_volume_mm=0.0,
            recommended_time="N/A",
            postponement_reason=f"High wind speed ({wind_speed_ms:.1f} m/s) impairs application uniformity.",
            decision_factors=factors,
            confidence=0.90,
        )

    # 1.4 Frost risk
    if temperature_c <= 2.0:
        factors.append(f"Low temperature ({temperature_c:.1f}°C) poses frost risk.")
        return DecisionOutcome(
            decision=IrrigationDecision.POSTPONED,
            priority=IrrigationPriority.NONE,
            recommended_volume_mm=0.0,
            recommended_time="N/A",
            postponement_reason=f"Freezing temperature hazard ({temperature_c:.1f}°C).",
            decision_factors=factors,
            confidence=0.95,
        )

    # 1.5 General weather unsuitable flag
    if weather_suitable is False:
        factors.append("General weather suitability assessment flagged as unsuitable.")
        return DecisionOutcome(
            decision=IrrigationDecision.POSTPONED,
            priority=IrrigationPriority.NONE,
            recommended_volume_mm=0.0,
            recommended_time="N/A",
            postponement_reason="Adverse meteorological conditions detected by Weather Agent.",
            decision_factors=factors,
            confidence=0.85,
        )

    # ------------------------------------------------------------------ #
    # Rule Group 2: Irrigation Requirement Evaluation
    # ------------------------------------------------------------------ #

    aw_pct = available_water_pct if available_water_pct is not None else 60.0

    # Moisture deficit triggers
    needs_water = (
        is_over_dry
        or soil_stress_index > 0.35
        or aw_pct < 45.0
    )

    if needs_water:
        # Determine Priority
        if is_over_dry or soil_stress_index >= 0.70 or aw_pct < 20.0:
            priority = IrrigationPriority.CRITICAL
            factors.append("Critical moisture deficit: plant approaching or at permanent wilting point.")
        elif soil_stress_index >= 0.45 or crop_growth_stage in ("mid", "development"):
            priority = IrrigationPriority.HIGH
            factors.append(f"Active growth stage '{crop_growth_stage}' with moderate water stress ({soil_stress_index:.2f}).")
        else:
            priority = IrrigationPriority.MEDIUM
            factors.append(f"Available water depleted to {aw_pct:.1f}% of TAW.")

        # Compute Net Irrigation Requirement (NIR)
        # Refill to ~85-90% of TAW to prevent runoff
        depletion_depth = max(0.0, (1.0 - (aw_pct / 100.0)) * water_holding_capacity_mm)
        target_volume = max(depletion_depth, etc_mm * 1.5)
        # Apply zone constraints
        recommended_volume = min(max_irrigation_mm, max(min_irrigation_mm, target_volume))

        # Schedule early morning (06:00 UTC) to minimize evaporative loss
        recommended_time = "06:00 UTC"
        factors.append(f"Recommended depth: {recommended_volume:.1f} mm to restore root zone moisture.")

        return DecisionOutcome(
            decision=IrrigationDecision.REQUIRED,
            priority=priority,
            recommended_volume_mm=round(recommended_volume, 1),
            recommended_time=recommended_time,
            postponement_reason=None,
            decision_factors=factors,
            confidence=0.92,
        )

    # ------------------------------------------------------------------ #
    # Rule Group 3: Irrigation NOT Required (Adequate Moisture)
    # ------------------------------------------------------------------ #
    factors.append(f"Root zone moisture adequate (Available Water: {aw_pct:.1f}%, Stress Index: {soil_stress_index:.2f}).")
    factors.append(f"Daily crop water demand ({etc_mm:.1f} mm ETc) safely supported by current soil storage.")

    return DecisionOutcome(
        decision=IrrigationDecision.NOT_REQUIRED,
        priority=IrrigationPriority.NONE,
        recommended_volume_mm=0.0,
        recommended_time="N/A",
        postponement_reason=None,
        decision_factors=factors,
        confidence=0.90,
    )

