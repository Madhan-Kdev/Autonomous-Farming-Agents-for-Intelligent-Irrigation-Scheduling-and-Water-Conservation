"""
Simulation and IoT Telemetry Control API Endpoints.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.common import APIResponse
from app.service.simulator import (
    ManualIrrigationResult,
    SimulationStepResult,
    VirtualFarmSimulator,
)

router = APIRouter(prefix="/simulation", tags=["IoT Simulation"])


class AdvanceSimulationRequest(BaseModel):
    farm_id: int
    target_date: date | None = None
    irrigation_events: dict[int, float] = Field(
        default_factory=dict,
        description="Zone ID -> Applied irrigation in mm.",
    )
    force_rain_mm: float | None = Field(
        default=None,
        description="Optional forced precipitation for scenario testing.",
    )


class SimulationStepOut(BaseModel):
    target_date: date
    weather_record_id: int
    soil_profiles_updated: list[int]
    simulated_et0_mm: float
    simulated_rain_mm: float
    zone_moisture_levels: dict[int, float]


class ManualIrrigationRequest(BaseModel):
    zone_id: int = Field(..., description="Target zone ID.")
    volume_mm: float | None = Field(default=None, description="Irrigation depth in mm.")
    volume_liters: float | None = Field(default=None, description="Irrigation volume in Liters.")
    irrigation_method: str | None = Field(
        default=None,
        description="Method: drip, sprinkler, flood, surface.",
    )
    flow_rate_l_h: float | None = Field(
        default=None,
        description="Pumping flow rate in L/h (default 25,000 L/h/ha).",
    )


class ManualIrrigationOut(BaseModel):
    zone_id: int
    zone_name: str
    farm_id: int
    volume_applied_mm: float
    volume_applied_liters: float
    duration_minutes: float
    flow_rate_l_h: float
    irrigation_method: str
    soil_moisture_before_pct: float
    soil_moisture_after_pct: float
    field_capacity_pct: float
    wilting_point_pct: float
    deep_percolation_mm: float
    stress_index_before: float
    stress_index_after: float
    irrigation_record_id: int
    soil_profile_id: int


@router.post("/advance", response_model=APIResponse[SimulationStepOut])
def advance_virtual_day(
    req: AdvanceSimulationRequest,
    db: Session = Depends(get_db),
):
    """
    Step the virtual farm simulation forward by one day.

    Updates:
    - Weather observations (temperature, humidity, solar radiation, rain).
    - Zone soil moisture levels based on crop ETc demand, rain, and irrigation inputs.
    """
    simulator = VirtualFarmSimulator(db)
    try:
        res: SimulationStepResult = simulator.advance_day(
            farm_id=req.farm_id,
            target_date=req.target_date,
            irrigation_events=req.irrigation_events,
            force_rain_mm=req.force_rain_mm,
        )
        data = SimulationStepOut(
            target_date=res.target_date,
            weather_record_id=res.weather_record_id,
            soil_profiles_updated=res.soil_profiles_updated,
            simulated_et0_mm=res.simulated_et0_mm,
            simulated_rain_mm=res.simulated_rain_mm,
            zone_moisture_levels=res.zone_moisture_levels,
        )
        return APIResponse(
            success=True,
            data=data,
            message=f"Simulation advanced to {res.target_date.isoformat()}.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/irrigate-manual", response_model=APIResponse[ManualIrrigationOut])
def apply_manual_irrigation(
    req: ManualIrrigationRequest,
    db: Session = Depends(get_db),
):
    """
    Execute an immediate manual irrigation command on a virtual farm zone.

    Updates soil moisture telemetry, checks for deep percolation loss,
    and commits an applied IrrigationRecord.
    """
    simulator = VirtualFarmSimulator(db)
    try:
        res = simulator.apply_zone_manual_irrigation(
            zone_id=req.zone_id,
            volume_mm=req.volume_mm,
            volume_liters=req.volume_liters,
            irrigation_method=req.irrigation_method,
            flow_rate_l_h=req.flow_rate_l_h,
        )
        data = ManualIrrigationOut(
            zone_id=res.zone_id,
            zone_name=res.zone_name,
            farm_id=res.farm_id,
            volume_applied_mm=res.volume_applied_mm,
            volume_applied_liters=res.volume_applied_liters,
            duration_minutes=res.duration_minutes,
            flow_rate_l_h=res.flow_rate_l_h,
            irrigation_method=res.irrigation_method,
            soil_moisture_before_pct=res.soil_moisture_before_pct,
            soil_moisture_after_pct=res.soil_moisture_after_pct,
            field_capacity_pct=res.field_capacity_pct,
            wilting_point_pct=res.wilting_point_pct,
            deep_percolation_mm=res.deep_percolation_mm,
            stress_index_before=res.stress_index_before,
            stress_index_after=res.stress_index_after,
            irrigation_record_id=res.irrigation_record_id,
            soil_profile_id=res.soil_profile_id,
        )
        return APIResponse(
            success=True,
            data=data,
            message=f"Manual irrigation of {res.volume_applied_mm} mm successfully applied to zone '{res.zone_name}'.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

