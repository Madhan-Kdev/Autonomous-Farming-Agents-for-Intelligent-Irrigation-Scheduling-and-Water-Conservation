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
from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
from app.schemas.common import APIResponse

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
# Endpoints
# ------------------------------------------------------------------ #

@router.get("", response_model=APIResponse[list[FarmOut]])
def list_farms(db: Session = Depends(get_db)):
    """Retrieve all active farms with their fields and zones."""
    farms = FarmRepository(db).get_all_active()
    farm_list = []
    field_repo = FieldRepository(db)
    zone_repo = ZoneRepository(db)

    for farm in farms:
        f_fields = field_repo.get_by_farm(farm.id)
        field_list = []
        for field in f_fields:
            f_zones = zone_repo.get_by_field(field.id)
            field_list.append(
                FieldOut(
                    id=field.id,
                    farm_id=field.farm_id,
                    name=field.name,
                    area_ha=field.area_ha,
                    soil_type=field.soil_type,
                    zones=[ZoneOut.model_validate(z) for z in f_zones],
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
    f_fields = field_repo.get_by_farm(farm.id)
    field_list = []
    for f in f_fields:
        f_zones = zone_repo.get_by_field(f.id)
        field_list.append(
            FieldOut(
                id=f.id,
                farm_id=f.farm_id,
                name=f.name,
                area_ha=f.area_ha,
                soil_type=f.soil_type,
                zones=[ZoneOut.model_validate(z) for z in f_zones],
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
