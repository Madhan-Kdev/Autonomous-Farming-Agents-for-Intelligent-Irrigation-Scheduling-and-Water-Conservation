"""
Reinforcement Learning Policy Benchmarking API Endpoints.

Provides:
- POST /api/v1/rl/benchmark:
    Evaluates current or simulated agricultural state under both the classical
    FAO-56 Rule-Based Decision Engine and the Deep Reinforcement Learning (PPO)
    Policy, returning side-by-side comparative analysis and action distributions.
"""

from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.models.farm import Farm
from app.models.zone import Zone
from app.schemas.common import APIResponse
from app.service.irrigation_rules import evaluate_irrigation_decision
from app.service.ppo_policy import PPOPolicyInference

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rl", tags=["Reinforcement Learning Policy"])


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------


class RLBenchmarkRequest(BaseModel):
    """Agricultural state parameters for policy benchmarking."""

    farm_id: int = Field(default=1, description="Farm ID")
    zone_id: int | None = Field(default=None, description="Optional Zone ID")

    soil_moisture_pct: float = Field(default=18.5, ge=0.0, le=100.0, description="Volumetric moisture %")
    field_capacity_pct: float = Field(default=30.0, ge=1.0, le=100.0, description="Field capacity %")
    wilting_point_pct: float = Field(default=12.0, ge=0.0, le=100.0, description="Permanent wilting point %")

    et0_mm: float = Field(default=5.2, ge=0.0, le=25.0, description="Reference ET0 mm")
    etc_mm: float = Field(default=5.8, ge=0.0, le=30.0, description="Crop ETc mm")
    forecast_rain_mm: float = Field(default=0.0, ge=0.0, le=200.0, description="Forecast rain mm")
    temperature_c: float = Field(default=28.5, ge=-20.0, le=60.0, description="Temperature °C")
    growth_stage: str = Field(default="mid", description="Stage: initial, development, mid, late")
    crop_name: str = Field(default="Wheat", description="Crop name")


class RuleDecisionSummary(BaseModel):
    decision: str = Field(..., description="REQUIRED, POSTPONED, NOT_REQUIRED")
    recommended_volume_mm: float
    recommended_duration_min: float
    priority: str
    urgency_score: float
    confidence: float
    rationale: str
    influencing_factors: list[str]


class PPOPolicySummary(BaseModel):
    action_mm: float
    action_name: str
    action_probabilities: dict[str, float]
    state_value: float
    policy_confidence: float
    crop_stress_anticipated: float
    water_saving_bias: float
    rationale: str
    feature_contributions: dict[str, float]


class PolicyComparisonOut(BaseModel):
    state_summary: dict[str, Any]
    rule_decision: RuleDecisionSummary
    ppo_policy: PPOPolicySummary
    volume_delta_mm: float = Field(
        ..., description="Rule volume - PPO volume (positive means PPO saved water)"
    )
    water_savings_vs_rule_pct: float = Field(
        ..., description="% water saved by PPO policy relative to rule-based engine"
    )
    alignment: str = Field(
        ..., description="AGREE, DEFICIT_SAVINGS, RAIN_HARVEST, or DIVERGENT"
    )
    synthesis: str = Field(..., description="Explainable comparison commentary")


# ---------------------------------------------------------------------------
# Endpoint implementation
# ---------------------------------------------------------------------------


@router.post("/benchmark", response_model=APIResponse[PolicyComparisonOut])
def benchmark_rl_policy(
    req: RLBenchmarkRequest,
    db: Session = Depends(get_db),
) -> APIResponse[PolicyComparisonOut]:
    """
    Run side-by-side benchmark comparing Rule-Based Engine vs PPO Policy.
    """
    if req.field_capacity_pct <= req.wilting_point_pct:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field capacity must be strictly greater than wilting point.",
        )

    # 1. Classical Rule-Based Decision Engine
    taw = max(req.field_capacity_pct - req.wilting_point_pct, 1.0)
    whc_mm = taw * 10.0 * 0.60
    is_over_wet = req.soil_moisture_pct >= req.field_capacity_pct
    is_over_dry = req.soil_moisture_pct <= req.wilting_point_pct + 1.0
    p = 0.50
    raw = p * taw
    depletion = max(0.0, req.field_capacity_pct - req.soil_moisture_pct)
    if depletion <= raw:
        ks = 0.0
    elif depletion >= taw:
        ks = 1.0
    else:
        ks = float(max(0.0, min(1.0, (depletion - raw) / ((1.0 - p) * taw))))

    avail_pct = max(0.0, min(100.0, ((req.soil_moisture_pct - req.wilting_point_pct) / taw) * 100.0))

    rule_res = evaluate_irrigation_decision(
        weather_suitable=req.forecast_rain_mm < 5.0 and req.temperature_c > 2.0,
        precipitation_mm=0.0,
        rainfall_forecast_mm=req.forecast_rain_mm,
        wind_speed_ms=2.5,
        temperature_c=req.temperature_c,
        is_over_wet=is_over_wet,
        is_over_dry=is_over_dry,
        soil_stress_index=ks,
        available_water_pct=avail_pct,
        water_holding_capacity_mm=whc_mm,
        etc_mm=req.etc_mm,
        crop_growth_stage=req.growth_stage,
    )

    rule_summary = RuleDecisionSummary(
        decision=rule_res.decision.value if hasattr(rule_res.decision, "value") else str(rule_res.decision),
        recommended_volume_mm=round(rule_res.recommended_volume_mm, 2),
        recommended_duration_min=round(rule_res.recommended_volume_mm * 10.0, 1),
        priority=rule_res.priority.value if hasattr(rule_res.priority, "value") else str(rule_res.priority),
        urgency_score=round(ks, 3),
        confidence=round(rule_res.confidence, 3),
        rationale=rule_res.postponement_reason or (
            f"Rule engine recommended {rule_res.recommended_volume_mm:.1f} mm "
            f"based on current root-zone depletion."
        ),
        influencing_factors=rule_res.decision_factors,
    )

    # 2. Deep Reinforcement Learning (PPO) Policy Engine
    ppo_engine = PPOPolicyInference()
    ppo_res = ppo_engine.evaluate_state(
        soil_moisture_pct=req.soil_moisture_pct,
        field_capacity_pct=req.field_capacity_pct,
        wilting_point_pct=req.wilting_point_pct,
        et0_mm=req.et0_mm,
        etc_mm=req.etc_mm,
        forecast_rain_mm=req.forecast_rain_mm,
        temperature_c=req.temperature_c,
        growth_stage=req.growth_stage,
    )

    ppo_summary = PPOPolicySummary(
        action_mm=ppo_res.action_mm,
        action_name=ppo_res.action_name,
        action_probabilities=ppo_res.action_probabilities,
        state_value=ppo_res.state_value,
        policy_confidence=ppo_res.policy_confidence,
        crop_stress_anticipated=ppo_res.crop_stress_anticipated,
        water_saving_bias=ppo_res.water_saving_bias,
        rationale=ppo_res.rationale,
        feature_contributions=ppo_res.feature_contributions,
    )

    # 3. Comparative Synthesis
    rule_vol = rule_summary.recommended_volume_mm
    ppo_vol = ppo_summary.action_mm
    delta_mm = round(rule_vol - ppo_vol, 2)

    if rule_vol > 0.001:
        savings_pct = round(max(0.0, (delta_mm / rule_vol) * 100.0), 1)
    else:
        savings_pct = 0.0

    # Determine alignment category
    if rule_summary.decision in ("POSTPONED", "NOT_REQUIRED") and ppo_vol == 0.0:
        alignment = "AGREE"
        synthesis = (
            "Both models agree that irrigation is NOT needed today. "
            "PPO policy confirms zero application to conserve water resources."
        )
    elif rule_summary.decision == "REQUIRED" and ppo_vol > 0.0:
        if abs(rule_vol - ppo_vol) <= 3.0:
            alignment = "AGREE"
            synthesis = (
                f"Both models agree irrigation is REQUIRED ({rule_vol:.1f} mm rule vs {ppo_vol:.1f} mm PPO). "
                f"Actions are tightly aligned within tolerance."
            )
        elif ppo_vol < rule_vol:
            alignment = "DEFICIT_SAVINGS"
            synthesis = (
                f"PPO recommends a deficit irrigation strategy of {ppo_vol:.1f} mm vs {rule_vol:.1f} mm rule-based, "
                f"yielding an estimated {savings_pct}% water savings while keeping anticipated stress safe (Ks={ppo_res.crop_stress_anticipated:.2f})."
            )
        else:
            alignment = "DIVERGENT"
            synthesis = (
                f"PPO policy allocated a larger buffer ({ppo_vol:.1f} mm vs {rule_vol:.1f} mm rule-based) "
                f"to prevent rapid drydown under elevated atmospheric demand."
            )
    elif req.forecast_rain_mm >= 5.0 and ppo_vol == 0.0:
        alignment = "RAIN_HARVEST"
        synthesis = (
            f"PPO policy halted irrigation completely to capitalize on {req.forecast_rain_mm:.1f} mm "
            f"forecast rainfall, eliminating deep drainage runoff."
        )
    else:
        alignment = "DIVERGENT"
        synthesis = (
            f"Model divergence: Rule engine decided {rule_summary.decision} ({rule_vol:.1f} mm) while "
            f"PPO policy selected {ppo_vol:.1f} mm. Review soil moisture thresholds and sensor confidence."
        )

    comparison_data = PolicyComparisonOut(
        state_summary={
            "soil_moisture_pct": req.soil_moisture_pct,
            "field_capacity_pct": req.field_capacity_pct,
            "wilting_point_pct": req.wilting_point_pct,
            "et0_mm": req.et0_mm,
            "etc_mm": req.etc_mm,
            "forecast_rain_mm": req.forecast_rain_mm,
            "temperature_c": req.temperature_c,
            "growth_stage": req.growth_stage,
            "crop_name": req.crop_name,
        },
        rule_decision=rule_summary,
        ppo_policy=ppo_summary,
        volume_delta_mm=delta_mm,
        water_savings_vs_rule_pct=savings_pct,
        alignment=alignment,
        synthesis=synthesis,
    )

    return APIResponse(
        success=True,
        data=comparison_data,
        message="PPO Policy vs Rule-Based benchmarking completed successfully.",
    )
