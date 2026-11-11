"""
ET0 and ETc Evapotranspiration API Endpoints (FAO-56 Penman-Monteith).
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.repositories.repositories import CropRepository, FarmRepository, WeatherRecordRepository
from app.schemas.common import APIResponse
from app.service.et0_calculator import ET0Inputs, FAO56PenmanMonteith, build_et0_inputs

router = APIRouter(prefix="/et0", tags=["Evapotranspiration & FAO-56"])


# ------------------------------------------------------------------ #
# Schemas
# ------------------------------------------------------------------ #

class ET0Step(BaseModel):
    step_number: int
    title: str
    fao_equation: str
    formula_latex: str
    result_value: float
    result_unit: str
    scientific_note: str


class CropETcOut(BaseModel):
    crop_name: str
    growth_stage: str
    kc: float
    etc_mm: float
    daily_water_liters_per_ha: float


class ET0DerivationOut(BaseModel):
    et0_mm: float
    radiation_term_mm: float
    aerodynamic_term_mm: float
    radiation_share_pct: float
    aerodynamic_share_pct: float
    t_mean_c: float
    pressure_kpa: float
    gamma_kpa_c: float
    es_kpa: float
    ea_kpa: float
    vpd_kpa: float
    delta_kpa_c: float
    ra_mj_m2: float
    rso_mj_m2: float
    rns_mj_m2: float
    rnl_mj_m2: float
    rn_mj_m2: float
    wind_speed_m_s: float
    solar_radiation_mj_m2: float
    crop_etc: CropETcOut | None = None
    steps: list[ET0Step]


class CalculateET0Request(BaseModel):
    temp_max_c: float = Field(..., description="Max air temperature (°C)")
    temp_min_c: float = Field(..., description="Min air temperature (°C)")
    humidity_max_pct: float = Field(default=75.0, description="Max relative humidity (%)")
    humidity_min_pct: float = Field(default=35.0, description="Min relative humidity (%)")
    wind_speed_m_s: float = Field(default=2.0, description="Wind speed at 2m (m/s)")
    solar_radiation_mj_m2: float = Field(default=20.0, description="Solar radiation (MJ/m²/day)")
    altitude_m: float = Field(default=100.0, description="Altitude (m)")
    latitude_deg: float = Field(default=18.5, description="Latitude (degrees)")
    day_of_year: int | None = Field(default=None, description="Day of year (1-365)")
    crop_name: str | None = Field(default=None, description="Optional crop name for ETc")
    growth_stage: str | None = Field(default="mid", description="Stage: initial, development, mid, late")
    custom_kc: float | None = Field(default=None, description="Optional direct Kc override")


# ------------------------------------------------------------------ #
# Endpoints
# ------------------------------------------------------------------ #

@router.get("/derivation", response_model=APIResponse[ET0DerivationOut])
def get_farm_et0_derivation(
    farm_id: int = Query(default=1, description="Target Farm ID"),
    crop_name: str | None = Query(default=None, description="Optional crop name for ETc"),
    growth_stage: str | None = Query(default="mid", description="Stage: initial, development, mid, late"),
    target_date: date | None = Query(default=None, description="Target date (defaults to latest)"),
    db: Session = Depends(get_db),
):
    """
    Retrieve live FAO-56 Penman-Monteith 13-step derivation breakdown for a farm.
    """
    farm = FarmRepository(db).get_by_id(farm_id)
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Farm {farm_id} not found.")

    weather_repo = WeatherRecordRepository(db)
    if target_date:
        w_rec = weather_repo.get_for_date(farm_id, target_date)
    else:
        recent = weather_repo.get_recent(farm_id, days=1)
        w_rec = recent[0] if recent else None

    doy = target_date.timetuple().tm_yday if target_date else date.today().timetuple().tm_yday

    if w_rec:
        inputs = ET0Inputs(
            temp_max_c=w_rec.temperature_max_c or 28.0,
            temp_min_c=w_rec.temperature_min_c or 18.0,
            humidity_max_pct=w_rec.humidity_max_pct or 75.0,
            humidity_min_pct=w_rec.humidity_min_pct or 35.0,
            humidity_mean_pct=w_rec.humidity_mean_pct or 55.0,
            wind_speed_m_s=w_rec.wind_speed_m_s or 2.2,
            solar_radiation_mj_m2=w_rec.solar_radiation_mj_m2 or 21.0,
            latitude_rad=math.radians(farm.latitude or 18.5204),
            altitude_m=float(farm.altitude_m or 100.0),
            day_of_year=doy,
        )
    else:
        # Fallback realistic weather for farm location
        inputs = ET0Inputs(
            temp_max_c=30.0,
            temp_min_c=20.0,
            humidity_max_pct=75.0,
            humidity_min_pct=35.0,
            humidity_mean_pct=55.0,
            wind_speed_m_s=2.5,
            solar_radiation_mj_m2=22.0,
            latitude_rad=math.radians(farm.latitude or 18.5204),
            altitude_m=float(farm.altitude_m or 100.0),
            day_of_year=doy,
        )

    calc = FAO56PenmanMonteith()
    derivation = calc.compute_derivation(inputs)

    # Compute crop ETc if crop requested
    crop_etc = None
    if crop_name:
        crop = CropRepository(db).get_by_name(crop_name)
        if crop:
            stage = (growth_stage or "mid").lower()
            if stage in ("initial", "ini"):
                kc = crop.kc_initial
            elif stage in ("development", "dev"):
                kc = round((crop.kc_initial + crop.kc_mid) / 2.0, 2)
            elif stage in ("late", "end"):
                kc = crop.kc_end
            else:
                kc = crop.kc_mid

            etc_val = round(derivation["et0_mm"] * kc, 2)
            liters_ha = round(etc_val * 10000.0, 1)
            crop_etc = CropETcOut(
                crop_name=crop.name,
                growth_stage=stage,
                kc=kc,
                etc_mm=etc_val,
                daily_water_liters_per_ha=liters_ha,
            )

    derivation["crop_etc"] = crop_etc
    return APIResponse(
        success=True,
        data=ET0DerivationOut(**derivation),
        message="FAO-56 Penman-Monteith derivation computed successfully.",
    )


@router.post("/calculate", response_model=APIResponse[ET0DerivationOut])
def calculate_custom_et0_derivation(
    req: CalculateET0Request,
    db: Session = Depends(get_db),
):
    """
    Calculate custom FAO-56 Penman-Monteith ET0 and crop ETc with complete derivation steps.
    """
    doy = req.day_of_year if req.day_of_year else date.today().timetuple().tm_yday
    inputs = ET0Inputs(
        temp_max_c=req.temp_max_c,
        temp_min_c=req.temp_min_c,
        humidity_max_pct=req.humidity_max_pct,
        humidity_min_pct=req.humidity_min_pct,
        wind_speed_m_s=req.wind_speed_m_s,
        solar_radiation_mj_m2=req.solar_radiation_mj_m2,
        latitude_rad=math.radians(req.latitude_deg),
        altitude_m=req.altitude_m,
        day_of_year=doy,
    )

    calc = FAO56PenmanMonteith()
    derivation = calc.compute_derivation(inputs)

    # Compute crop ETc
    crop_etc = None
    if req.custom_kc is not None:
        kc = float(req.custom_kc)
        etc_val = round(derivation["et0_mm"] * kc, 2)
        crop_etc = CropETcOut(
            crop_name=req.crop_name or "Custom Crop",
            growth_stage=req.growth_stage or "custom",
            kc=kc,
            etc_mm=etc_val,
            daily_water_liters_per_ha=round(etc_val * 10000.0, 1),
        )
    elif req.crop_name:
        crop = CropRepository(db).get_by_name(req.crop_name)
        if crop:
            stage = (req.growth_stage or "mid").lower()
            if stage in ("initial", "ini"):
                kc = crop.kc_initial
            elif stage in ("development", "dev"):
                kc = round((crop.kc_initial + crop.kc_mid) / 2.0, 2)
            elif stage in ("late", "end"):
                kc = crop.kc_end
            else:
                kc = crop.kc_mid

            etc_val = round(derivation["et0_mm"] * kc, 2)
            crop_etc = CropETcOut(
                crop_name=crop.name,
                growth_stage=stage,
                kc=kc,
                etc_mm=etc_val,
                daily_water_liters_per_ha=round(etc_val * 10000.0, 1),
            )

    derivation["crop_etc"] = crop_etc
    return APIResponse(
        success=True,
        data=ET0DerivationOut(**derivation),
        message="Custom FAO-56 Penman-Monteith derivation computed successfully.",
    )
