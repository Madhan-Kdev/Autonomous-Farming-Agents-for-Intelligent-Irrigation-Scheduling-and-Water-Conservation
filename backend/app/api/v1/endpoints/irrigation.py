"""
Dedicated Irrigation Decision API Endpoints.

Provides:
- POST /api/v1/irrigation/decision: Execute multi-agent irrigation decision with custom agricultural inputs
- GET /api/v1/irrigation/history: Query persistent execution history across zones and farms
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.models.irrigation import IrrigationRecord
from app.repositories.repositories import (
    AgentExecutionLogRepository,
    FarmRepository,
    IrrigationRecordRepository,
    ZoneRepository,
)
from app.schemas.agent_state import AgentState, RequestContext
from app.schemas.common import APIResponse
from app.workflow.agent_workflow import create_agent_workflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/irrigation", tags=["Irrigation Decision"])


class IrrigationDecisionRequest(BaseModel):
    farm_id: int = Field(..., description="Target farm ID")
    field_id: int | None = Field(default=None, description="Target field ID")
    zone_id: int | None = Field(default=None, description="Target zone ID")
    crop_type: str | None = Field(default=None, description="Crop name (e.g. Wheat, Tomato, Maize)")
    growth_stage: str | None = Field(default=None, description="Crop growth stage: initial, development, mid, late")

    # Soil inputs
    soil_moisture: float | None = Field(default=None, ge=0.0, le=100.0, description="Volumetric soil moisture %")
    field_capacity: float | None = Field(default=None, ge=1.0, le=100.0, description="Field capacity %")
    wilting_point: float | None = Field(default=None, ge=0.0, le=100.0, description="Permanent wilting point %")
    soil_type: str | None = Field(default=None, description="Soil texture type")

    # Weather inputs
    temperature: float | None = Field(default=None, ge=-30.0, le=65.0, description="Ambient temperature (°C)")
    humidity: float | None = Field(default=None, ge=0.0, le=100.0, description="Relative humidity (%)")
    wind_speed: float | None = Field(default=None, ge=0.0, le=50.0, description="Wind speed (m/s)")
    rainfall: float | None = Field(default=None, ge=0.0, le=300.0, description="Observed rainfall (mm)")
    rain_probability: float | None = Field(default=None, ge=0.0, le=100.0, description="Rain probability (%)")
    forecast_rainfall: float | None = Field(default=None, ge=0.0, le=300.0, description="Forecast rainfall (mm)")

    # Water availability inputs
    water_availability: str | None = Field(default=None, description="Status: Normal, Limited, Low, Critical")
    available_water_liters: float | None = Field(default=None, ge=0.0, description="Available water quantity in Liters")

    # Execution toggles
    use_historical_data: bool = Field(default=True, description="Enable historical audit analysis")
    use_et0_prediction: bool = Field(default=True, description="Enable ML ET0 regressor forecast")
    run_full_workflow: bool = Field(default=True, description="Execute full 10-node multi-agent pipeline")
    user_notes: str | None = Field(default=None, description="Optional notes or scenario tags")

    @model_validator(mode="after")
    def validate_soil_bounds(self) -> IrrigationDecisionRequest:
        if self.field_capacity is not None and self.wilting_point is not None:
            if self.field_capacity <= self.wilting_point:
                raise ValueError(
                    f"Field Capacity ({self.field_capacity}%) must be strictly greater than "
                    f"Wilting Point ({self.wilting_point}%)."
                )
        return self


@router.post("/decision", response_model=APIResponse[AgentState])
def execute_irrigation_decision(
    req: IrrigationDecisionRequest,
    db: Session = Depends(get_db),
):
    farm = FarmRepository(db).get_by_id(req.farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm {req.farm_id} not found.",
        )

    zone_ids = [req.zone_id] if req.zone_id is not None else []

    initial_state = AgentState()
    initial_state.request = RequestContext(
        farm_id=req.farm_id,
        field_id=req.field_id,
        zone_ids=zone_ids,
        crop_type=req.crop_type,
        location_latitude=farm.latitude,
        location_longitude=farm.longitude,
        target_date=date.today(),
        user_notes=req.user_notes or "Interactive decision request",
        override_temperature_c=req.temperature,
        override_humidity_pct=req.humidity,
        override_wind_speed_ms=req.wind_speed,
        override_rainfall_mm=req.rainfall,
        override_rain_probability_pct=req.rain_probability,
        override_forecast_rainfall_mm=req.forecast_rainfall,
        override_soil_moisture_pct=req.soil_moisture,
        override_growth_stage=req.growth_stage,
        override_field_capacity_pct=req.field_capacity,
        override_wilting_point_pct=req.wilting_point,
        override_soil_type=req.soil_type,
        override_water_availability_status=req.water_availability,
        override_available_water_liters=req.available_water_liters,
        use_historical_data=req.use_historical_data,
        use_et0_prediction=req.use_et0_prediction,
        run_full_workflow=req.run_full_workflow,
    )

    workflow = create_agent_workflow(db)
    result_raw = workflow.invoke(initial_state)

    if isinstance(result_raw, dict):
        result_state = AgentState.model_validate(result_raw)
    else:
        result_state = result_raw

    # Persist decision event into audit history table
    target_zone_id = req.zone_id
    if not target_zone_id:
        for fld in farm.fields:
            if fld.zones:
                target_zone_id = fld.zones[0].id
                break

    if target_zone_id:
        try:
            decision_val = (
                result_state.irrigation_decision.decision.value
                if hasattr(result_state.irrigation_decision.decision, "value")
                else str(result_state.irrigation_decision.decision)
            )
            vol_mm = result_state.irrigation_decision.recommended_volume_mm or 0.0
            rec = IrrigationRecord(
                farm_id=req.farm_id,
                zone_id=target_zone_id,
                scheduled_at=datetime.now(timezone.utc),
                decision=decision_val,
                recommended_volume_mm=vol_mm,
                recommended_duration_min=vol_mm * 10.0 if vol_mm else 0.0,
                actual_volume_mm=vol_mm if decision_val == "REQUIRED" else 0.0,
                was_applied=(decision_val == "REQUIRED"),
                soil_moisture_before_pct=result_state.soil.soil_moisture_pct,
                et0_on_day_mm=result_state.et0.et0_reference_mm,
                etc_on_day_mm=result_state.et0.etc_mm,
                precipitation_on_day_mm=result_state.weather.rainfall_mm,
                decision_confidence=result_state.irrigation_decision.confidence or 0.95,
                reasoning_summary=(
                    result_state.irrigation_decision.postponement_reason
                    or result_state.advisory.recommended_action
                    or "Autonomous LangGraph scheduling run"
                ),
            )
            db.add(rec)
            db.commit()
        except Exception as e:
            logger.warning(f"Could not persist irrigation history record: {e}")
            db.rollback()

    return APIResponse(
        success=True,
        data=result_state,
        message="Autonomous irrigation decision analysis completed successfully.",
    )


@router.get("/history", response_model=APIResponse[list[dict[str, Any]]])
def get_irrigation_decision_history(
    farm_id: int | None = Query(default=None, description="Filter by farm ID"),
    zone_id: int | None = Query(default=None, description="Filter by zone ID"),
    limit: int = Query(default=30, ge=1, le=100, description="Max records to return"),
    db: Session = Depends(get_db),
):
    stmt = select(IrrigationRecord).order_by(IrrigationRecord.scheduled_at.desc())
    if farm_id is not None:
        stmt = stmt.where(IrrigationRecord.farm_id == farm_id)
    if zone_id is not None:
        stmt = stmt.where(IrrigationRecord.zone_id == zone_id)

    stmt = stmt.limit(limit)
    records = db.execute(stmt).scalars().all()

    data = [
        {
            "id": r.id,
            "farm_id": r.farm_id,
            "zone_id": r.zone_id,
            "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
            "decision": r.decision,
            "recommended_volume_mm": r.recommended_volume_mm,
            "recommended_duration_min": r.recommended_duration_min,
            "actual_volume_mm": r.actual_volume_mm,
            "was_applied": r.was_applied,
            "soil_moisture_before_pct": r.soil_moisture_before_pct,
            "soil_moisture_after_pct": r.soil_moisture_after_pct,
            "et0_on_day_mm": r.et0_on_day_mm,
            "etc_on_day_mm": r.etc_on_day_mm,
            "precipitation_on_day_mm": r.precipitation_on_day_mm,
            "decision_confidence": r.decision_confidence,
            "irrigation_method": r.irrigation_method,
            "reasoning_summary": r.reasoning_summary,
        }
        for r in records
    ]

    return APIResponse(
        success=True,
        data=data,
        message="Irrigation decision history retrieved successfully.",
    )
