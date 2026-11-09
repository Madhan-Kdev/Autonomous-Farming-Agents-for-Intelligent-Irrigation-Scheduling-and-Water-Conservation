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
from app.service.simulator import SimulationStepResult, VirtualFarmSimulator

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

