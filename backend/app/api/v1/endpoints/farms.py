"""
Farms, Fields, and Zones API Endpoints.
"""

from __future__ import annotations

import logging
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.repositories.repositories import FarmRepository, FieldRepository, SoilProfileRepository, ZoneRepository
from app.schemas.common import APIResponse
from app.service.soil_physics import compute_soil_water_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/farms", tags=["Farms & Fields"])


# ------------------------------------------------------------------ #
# Schemas
# ------------------------------------------------------------------ #

class ZoneOut(BaseModel):
    id: int
    field_id: int
    zone_number: int
    name: str
    area_ha: float
    crop_name: str | None
    irrigation_method: str | None
    is_active: bool
    min_irrigation_mm: float | None
    max_irrigation_mm: float | None
    latest_soil_moisture_pct: float | None = None
    field_capacity_pct: float | None = None
    wilting_point_pct: float | None = None
    stress_index: float | None = None

    class Config:
        from_attributes = True


class FieldOut(BaseModel):
    id: int
    farm_id: int
    name: str
    area_ha: float
    soil_type: str | None
    zones: list[ZoneOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class FarmOut(BaseModel):
    id: int
    name: str
    owner_name: str | None
    latitude: float
    longitude: float
    altitude_m: float | None
    total_area_ha: float | None
    fields: list[FieldOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _build_zone_out(z, latest_soil) -> ZoneOut:
    moisture = latest_soil.volumetric_moisture_pct if latest_soil else None
    fc = latest_soil.field_capacity_pct if latest_soil else None
    wp = latest_soil.wilting_point_pct if latest_soil else None
    stress = None
    if moisture is not None and fc is not None and wp is not None:
        root_m = (latest_soil.depth_cm / 100.0) if (latest_soil and latest_soil.depth_cm) else 0.40
        status = compute_soil_water_status(
            moisture_pct=moisture,
            field_capacity_pct=fc,
            wilting_point_pct=wp,
            root_depth_m=root_m,
        )
        stress = round(status.soil_stress_index, 4)

    return ZoneOut(
        id=z.id,
        field_id=z.field_id,
        zone_number=z.zone_number,
        name=z.name,
        area_ha=z.area_ha,
        crop_name=z.crop_name,
        irrigation_method=z.irrigation_method,
        is_active=z.is_active,
        min_irrigation_mm=z.min_irrigation_mm,
        max_irrigation_mm=z.max_irrigation_mm,
        latest_soil_moisture_pct=moisture,
        field_capacity_pct=fc,
        wilting_point_pct=wp,
        stress_index=stress,
    )


# ------------------------------------------------------------------ #
# Endpoints
# ------------------------------------------------------------------ #

@router.get("", response_model=APIResponse[list[FarmOut]])
def list_farms(db: Session = Depends(get_db)):
    """Retrieve all active farms with their fields and zones."""
    farms = FarmRepository(db).get_all_active()
    farm_list = []
    field_repo = FieldRepository(db)
    zone_repo = ZoneRepository(db)
    soil_repo = SoilProfileRepository(db)

    for farm in farms:
        f_fields = field_repo.get_by_farm(farm.id)
        field_list = []
        for field in f_fields:
            f_zones = zone_repo.get_by_field(field.id)
            z_outs = [
                _build_zone_out(z, soil_repo.get_latest_for_zone(z.id))
                for z in f_zones
            ]
            field_list.append(
                FieldOut(
                    id=field.id,
                    farm_id=field.farm_id,
                    name=field.name,
                    area_ha=field.area_ha,
                    soil_type=field.soil_type,
                    zones=z_outs,
                )
            )
        farm_list.append(
            FarmOut(
                id=farm.id,
                name=farm.name,
                owner_name=farm.owner_name,
                latitude=farm.latitude,
                longitude=farm.longitude,
                altitude_m=farm.altitude_m,
                total_area_ha=farm.total_area_ha,
                fields=field_list,
            )
        )
    return APIResponse(success=True, data=farm_list, message="Farms retrieved successfully.")


@router.get("/{farm_id}", response_model=APIResponse[FarmOut])
def get_farm(farm_id: int, db: Session = Depends(get_db)):
    """Retrieve details of a single farm."""
    farm = FarmRepository(db).get_by_id(farm_id)
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Farm {farm_id} not found.")

    field_repo = FieldRepository(db)
    zone_repo = ZoneRepository(db)
    soil_repo = SoilProfileRepository(db)
    f_fields = field_repo.get_by_farm(farm.id)
    field_list = []
    for f in f_fields:
        f_zones = zone_repo.get_by_field(f.id)
        z_outs = [
            _build_zone_out(z, soil_repo.get_latest_for_zone(z.id))
            for z in f_zones
        ]
        field_list.append(
            FieldOut(
                id=f.id,
                farm_id=f.farm_id,
                name=f.name,
                area_ha=f.area_ha,
                soil_type=f.soil_type,
                zones=z_outs,
            )
        )

    return APIResponse(
        success=True,
        data=FarmOut(
            id=farm.id,
            name=farm.name,
            owner_name=farm.owner_name,
            latitude=farm.latitude,
            longitude=farm.longitude,
            altitude_m=farm.altitude_m,
            total_area_ha=farm.total_area_ha,
            fields=field_list,
        ),
        message="Farm retrieved successfully.",
    )
