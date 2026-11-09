"""
Crops Reference API Endpoints.
"""

from __future__ import annotations

import logging
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.repositories.repositories import CropRepository
from app.schemas.common import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crops", tags=["Crops"])


class CropOut(BaseModel):
    id: int
    name: str
    scientific_name: str | None
    crop_type: str | None
    kc_initial: float
    kc_mid: float
    kc_end: float
    root_depth_initial_m: float
    root_depth_max_m: float
    depletion_fraction_p: float
    days_initial: int
    days_development: int
    days_mid: int
    days_late: int
    total_growing_days: int

    class Config:
        from_attributes = True


@router.get("", response_model=APIResponse[list[CropOut]])
def list_crops(db: Session = Depends(get_db)):
    """Retrieve all standard FAO-56 crop profiles."""
    crops = CropRepository(db).get_all_crops()
    return APIResponse(
        success=True,
        data=[CropOut.model_validate(c) for c in crops],
        message="Crops retrieved successfully.",
    )


@router.get("/{crop_name}", response_model=APIResponse[CropOut])
def get_crop(crop_name: str, db: Session = Depends(get_db)):
    """Retrieve details for a specific crop by name."""
    crop = CropRepository(db).get_by_name(crop_name)
    if not crop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crop {crop_name!r} not found.")
    return APIResponse(
        success=True,
        data=CropOut.model_validate(crop),
        message=f"Crop {crop_name} retrieved successfully.",
    )
