"""
Shared agent state schema for the Autonomous Farming Agents system.

This is the central data contract that flows through the entire LangGraph
workflow.  Every agent reads from and writes into this state object.

Design principles
-----------------
* All sections are optional at initialisation — agents populate them as
  the workflow progresses.
* Every section is a typed Pydantic model, NOT a free-form dict.
* The state is serialisable to JSON so it can be persisted, replayed, and
  inspected for debugging.
* Agents must NOT invent values; they must derive them from inputs or
  validated computations.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ================================================================== #
# Enumerations
# ================================================================== #


class IrrigationDecision(str, Enum):
    """Top-level irrigation decision produced by the Decision Agent."""

    REQUIRED = "REQUIRED"
    POSTPONED = "POSTPONED"
    NOT_REQUIRED = "NOT_REQUIRED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class IrrigationPriority(str, Enum):
    """Priority level attached to an irrigation recommendation."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class RiskSeverity(str, Enum):
    """Severity level for detected risks and anomalies."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AgentStatus(str, Enum):
    """Execution status for a single agent step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# ================================================================== #
# Sub-models — populated by individual agents
# ================================================================== #


class RequestContext(BaseModel):
    """Initial user request context passed into the workflow."""

    farm_id: int | None = None
    field_id: int | None = None
    zone_ids: list[int] = Field(default_factory=list)
    crop_type: str | None = None
    location_latitude: float | None = None
    location_longitude: float | None = None
    target_date: date | None = None
    user_notes: str | None = None
    # Scenario sandbox overrides
    override_temperature_c: float | None = None
    override_humidity_pct: float | None = None
    override_wind_speed_ms: float | None = None
    override_rainfall_mm: float | None = None
    override_solar_radiation_mjm2: float | None = None
    override_soil_moisture_pct: float | None = None
    override_growth_stage: str | None = None
    override_field_capacity_pct: float | None = None
    override_wilting_point_pct: float | None = None
    override_soil_type: str | None = None
    override_rain_probability_pct: float | None = None
    override_forecast_rainfall_mm: float | None = None
    override_water_availability_status: str | None = None  # "Normal", "Limited", "Low", "Critical"
    override_available_water_liters: float | None = None
    use_historical_data: bool = True
    use_et0_prediction: bool = True
    run_full_workflow: bool = True


class WeatherContext(BaseModel):
    """
    Structured weather intelligence produced by the Weather Agent.

    All numerical values must originate from validated API responses or
    historical data — never from LLM inference.
    """

    temperature_c: float | None = None
    humidity_pct: float | None = None
    wind_speed_ms: float | None = None
    rainfall_mm: float | None = None
    solar_radiation_mjm2: float | None = None
    rainfall_probability_pct: float | None = None
    forecast_rainfall_7d_mm: float | None = None
    irrigation_suitable: bool | None = None
    weather_risk_level: str | None = None
    weather_summary: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_source: str = ""
    evidence: list[str] = Field(default_factory=list)


class SoilContext(BaseModel):
    """
    Zone-level soil intelligence produced by the Soil Agent.

    Uses simulated/virtual sensor telemetry — NOT physical sensors.
    """

    zone_id: int | None = None
    soil_type: str | None = None
    soil_moisture_pct: float | None = None
    field_capacity_pct: float | None = None
    wilting_point_pct: float | None = None
    available_water_pct: float | None = None
    water_holding_capacity_mm: float | None = None
    soil_stress_index: float = Field(default=0.0, ge=0.0, le=1.0)
    is_over_wet: bool = False
    is_over_dry: bool = False
    soil_condition: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    data_source: str = "simulated"


class CropContext(BaseModel):
    """
    Crop intelligence produced by the Crop Agent.

    Kc values must come from FAO-56 validated tables — not LLM estimates.
    """

    crop_type: str | None = None
    growth_stage: str | None = None
    crop_coefficient_kc: float | None = None
    root_depth_m: float | None = None
    crop_water_requirement_mm: float | None = None
    crop_stress_index: float = Field(default=0.0, ge=0.0, le=1.0)
    water_demand_category: str = ""
    crop_condition: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class ET0Context(BaseModel):
    """
    Evapotranspiration data from both calculation and ML prediction.

    Reference ET₀ is calculated using FAO-56 Penman-Monteith.
    Predicted ET₀ comes from the trained LSTM/ANN model.
    """

    et0_reference_mm: float | None = None        # FAO-56 calculated
    et0_predicted_mm: float | None = None         # ML model output
    etc_mm: float | None = None                   # ETc = ET0 × Kc
    calculation_method: str = ""
    prediction_model: str = ""
    prediction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class HistoricalContext(BaseModel):
    """
    Historical data intelligence produced by the Historical Agent.

    Provides pattern-based context rather than raw historical records.
    """

    avg_rainfall_30d_mm: float | None = None
    avg_irrigation_7d_mm: float | None = None
    historical_water_usage_l: float | None = None
    detected_over_irrigation: bool = False
    detected_under_irrigation: bool = False
    seasonal_demand_pattern: str = ""
    historical_summary: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class ZoneIrrigationPlan(BaseModel):
    """Irrigation plan for a single farm zone, produced by Zone Agents."""

    zone_id: int
    zone_name: str = ""
    irrigation_required: bool = False
    recommended_volume_mm: float = 0.0
    priority: IrrigationPriority = IrrigationPriority.NONE
    stress_index: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)

    # Multi-zone coordination & hydraulic deconfliction attributes
    crop_name: str = ""
    area_ha: float = 1.0
    irrigation_method: str = "drip"
    flow_rate_l_h: float = 25000.0
    volume_liters: float = 0.0
    duration_minutes: float = 0.0
    start_time: str = ""
    end_time: str = ""
    sequence_order: int = 1
    conflict_detected: bool = False
    rationing_applied: bool = False
    original_volume_mm: float | None = None


class IrrigationDecisionContext(BaseModel):
    """
    Structured irrigation decision produced by the Irrigation Decision Agent.

    Numerical quantities must originate from agricultural calculations or
    validated model outputs — NOT from LLM reasoning.
    """

    decision: IrrigationDecision = IrrigationDecision.INSUFFICIENT_DATA
    priority: IrrigationPriority = IrrigationPriority.NONE
    recommended_time: str | None = None          # ISO-8601 or "HH:MM"
    recommended_volume_mm: float | None = None
    affected_zones: list[int] = Field(default_factory=list)
    postponement_reason: str | None = None
    decision_factors: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class OptimizationContext(BaseModel):
    """
    Water optimization output from the Water Optimization Agent.

    All saving percentages must be calculated from actual data.
    """

    baseline_volume_mm: float | None = None
    optimized_volume_mm: float | None = None
    water_saving_mm: float | None = None
    water_saving_pct: float | None = None
    over_irrigation_detected: bool = False
    under_irrigation_risk: bool = False
    optimization_method: str = ""
    evidence: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    """A single identified risk or anomaly."""

    risk_type: str
    severity: RiskSeverity
    description: str
    evidence: list[str] = Field(default_factory=list)
    mitigation: str = ""


class RiskContext(BaseModel):
    """Risk and anomaly detection results from the Risk Agent."""

    risks: list[RiskItem] = Field(default_factory=list)
    overall_risk_level: RiskSeverity = RiskSeverity.INFO
    recommendation_safe: bool = True
    risk_summary: str = ""


class AdvisoryContext(BaseModel):
    """
    Farmer-friendly explanation produced by the XAI / Advisory Agent.

    Every statement in the explanation must be grounded in actual
    structured outputs — not fabricated by the LLM.
    """

    irrigation_required: bool = False
    recommended_action: str = ""
    recommended_time: str | None = None
    recommended_volume_mm: float | None = None
    target_zones: list[int] = Field(default_factory=list)
    weather_influence: str = ""
    soil_influence: str = ""
    crop_influence: str = ""
    et0_influence: str = ""
    rainfall_influence: str = ""
    risk_summary: str = ""
    water_conservation_summary: str = ""
    full_explanation: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AgentExecutionRecord(BaseModel):
    """Records the execution metadata for a single agent step."""

    agent_name: str
    status: AgentStatus = AgentStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    error_message: str | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    confidence: float | None = None


# ================================================================== #
# Master State
# ================================================================== #


class AgentState(BaseModel):
    """
    The single shared state object that flows through the LangGraph workflow.

    All agents read from and write into this state.  The orchestrator
    initialises it from the user request and passes it sequentially
    through the agent graph.

    Immutability contract
    ---------------------
    Agents must not mutate previous agents' output sections.  They write
    only to their designated section.  The orchestrator is the only
    component allowed to coordinate across sections.
    """

    # ---- Identity ---------------------------------------- #
    run_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this orchestration run.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # ---- User Request ------------------------------------ #
    request: RequestContext = Field(default_factory=RequestContext)

    # ---- Agent Outputs ----------------------------------- #
    weather: WeatherContext = Field(default_factory=WeatherContext)
    soil: SoilContext = Field(default_factory=SoilContext)
    crop: CropContext = Field(default_factory=CropContext)
    et0: ET0Context = Field(default_factory=ET0Context)
    historical: HistoricalContext = Field(default_factory=HistoricalContext)
    zone_plans: list[ZoneIrrigationPlan] = Field(default_factory=list)
    irrigation_decision: IrrigationDecisionContext = Field(
        default_factory=IrrigationDecisionContext
    )
    optimization: OptimizationContext = Field(default_factory=OptimizationContext)
    risk: RiskContext = Field(default_factory=RiskContext)
    advisory: AdvisoryContext = Field(default_factory=AdvisoryContext)

    # ---- Execution Metadata ------------------------------ #
    agent_executions: list[AgentExecutionRecord] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    workflow_step: str = "INITIALISED"
    is_complete: bool = False

    # ---- Raw LLM scratch (not exposed in final output) --- #
    llm_scratch: dict[str, Any] = Field(
        default_factory=dict,
        description="Temporary LLM reasoning scratch — not part of final output.",
    )
