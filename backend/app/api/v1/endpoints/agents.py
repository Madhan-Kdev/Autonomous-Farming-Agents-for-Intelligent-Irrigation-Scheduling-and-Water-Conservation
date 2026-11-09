"""
Agent Orchestration and Execution API Endpoints.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.repositories.repositories import FarmRepository, ZoneRepository
from app.schemas.agent_state import AgentState, RequestContext
from app.schemas.common import APIResponse
from app.workflow.agent_workflow import create_agent_workflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["Agent Orchestration"])


# ------------------------------------------------------------------ #
# Request & Response Schemas
# ------------------------------------------------------------------ #

class TriggerWorkflowRequest(BaseModel):
    farm_id: int
    field_id: int | None = None
    zone_ids: list[int] = Field(default_factory=list)
    crop_type: str | None = None
    target_date: date | None = None
    user_notes: str | None = None
    # Scenario simulation overrides
    override_temperature_c: float | None = None
    override_humidity_pct: float | None = None
    override_wind_speed_ms: float | None = None
    override_rainfall_mm: float | None = None
    override_solar_radiation_mjm2: float | None = None
    override_soil_moisture_pct: float | None = None


# ------------------------------------------------------------------ #
# Endpoints
# ------------------------------------------------------------------ #

@router.post("/run", response_model=APIResponse[AgentState])
def run_orchestration_workflow(
    req: TriggerWorkflowRequest,
    db: Session = Depends(get_db),
):
    """
    Trigger the multi-agent LangGraph workflow across all 10 specialized agents.

    Executes:
    1. WeatherAgent
    2. SoilAgent
    3. CropAgent
    4. ET0PredictionModule
    5. HistoricalAgent
    6. IrrigationDecisionAgent
    7. ZoneIrrigationAgent
    8. WaterOptimizationAgent
    9. RiskAnomalyAgent
    10. FarmerAdvisoryAgent
    """
    farm = FarmRepository(db).get_by_id(req.farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm {req.farm_id} not found.",
        )

    # Initialize State
    initial_state = AgentState()
    initial_state.request = RequestContext(
        farm_id=req.farm_id,
        field_id=req.field_id,
        zone_ids=req.zone_ids,
        crop_type=req.crop_type,
        location_latitude=farm.latitude,
        location_longitude=farm.longitude,
        target_date=req.target_date,
        user_notes=req.user_notes,
        override_temperature_c=req.override_temperature_c,
        override_humidity_pct=req.override_humidity_pct,
        override_wind_speed_ms=req.override_wind_speed_ms,
        override_rainfall_mm=req.override_rainfall_mm,
        override_solar_radiation_mjm2=req.override_solar_radiation_mjm2,
        override_soil_moisture_pct=req.override_soil_moisture_pct,
    )

    # Compile and invoke workflow
    workflow = create_agent_workflow(db)
    result_raw = workflow.invoke(initial_state)

    if isinstance(result_raw, dict):
        result_state = AgentState.model_validate(result_raw)
    else:
        result_state = result_raw

    return APIResponse(
        success=True,
        data=result_state,
        message="Multi-agent orchestration workflow completed successfully.",
    )


@router.get("/zones/{zone_id}/history", response_model=APIResponse[list[dict[str, Any]]])
def get_zone_irrigation_history(
    zone_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve historical irrigation records and execution history for a zone."""
    from app.repositories.repositories import IrrigationRecordRepository

    records = IrrigationRecordRepository(db).get_recent_for_zone(zone_id, limit=30)
    data = [
        {
            "id": r.id,
            "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
            "decision": r.decision,
            "recommended_volume_mm": r.recommended_volume_mm,
            "actual_volume_mm": r.actual_volume_mm,
            "was_applied": r.was_applied,
            "reasoning_summary": r.reasoning_summary,
        }
        for r in records
    ]
    return APIResponse(
        success=True,
        data=data,
        message=f"Irrigation history for zone {zone_id} retrieved successfully.",
    )
