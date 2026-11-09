"""
Soil Physics & FAO-56 Soil Moisture Equations.

Implements standard soil water balance calculations according to FAO-56:
- Total Available Water (TAW, mm)
- Readily Available Water (RAW, mm)
- Available Water Percentage (AW%)
- Soil Water Depletion (Dr, mm)
- Soil Water Stress Coefficient (Ks) and Stress Index (1 - Ks)

Reference:
    Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998).
    Crop evapotranspiration — Guidelines for computing crop water
    requirements. FAO Irrigation and Drainage Paper 56, Chapter 8.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Standard soil texture hydraulic properties (FAO-56 Table 19 reference values)
SOIL_TEXTURE_DEFAULTS = {
    "Sand": {"fc": 10.0, "wp": 4.0},
    "Loamy Sand": {"fc": 15.0, "wp": 6.0},
    "Sandy Loam": {"fc": 22.0, "wp": 10.0},
    "Loam": {"fc": 27.0, "wp": 12.0},
    "Silt Loam": {"fc": 33.0, "wp": 13.0},
    "Silt": {"fc": 31.0, "wp": 9.0},
    "Sandy Clay Loam": {"fc": 28.0, "wp": 15.0},
    "Clay Loam": {"fc": 32.0, "wp": 18.0},
    "Silty Clay Loam": {"fc": 37.0, "wp": 21.0},
    "Sandy Clay": {"fc": 29.0, "wp": 19.0},
    "Silty Clay": {"fc": 41.0, "wp": 25.0},
    "Clay": {"fc": 40.0, "wp": 27.0},
}


@dataclass
class SoilWaterStatus:
    """Calculated soil moisture balance status."""

    volumetric_moisture_pct: float
    field_capacity_pct: float
    wilting_point_pct: float
    root_depth_m: float
    depletion_fraction_p: float
    taw_mm: float
    raw_mm: float
    depletion_mm: float
    available_water_pct: float
    ks: float
    soil_stress_index: float
    is_over_wet: bool
    is_over_dry: bool
    condition_label: str


def compute_soil_water_status(
    moisture_pct: float,
    field_capacity_pct: float,
    wilting_point_pct: float,
    root_depth_m: float = 0.3,
    depletion_fraction_p: float = 0.5,
) -> SoilWaterStatus:
    """
    Compute soil water balance parameters and FAO-56 stress index.

    Parameters
    ----------
    moisture_pct : float
        Current volumetric soil moisture (theta, %).
    field_capacity_pct : float
        Field capacity volumetric moisture (theta_FC, %).
    wilting_point_pct : float
        Permanent wilting point volumetric moisture (theta_WP, %).
    root_depth_m : float
        Effective root depth (Zr) in meters.
    depletion_fraction_p : float
        Fraction of TAW that can be depleted before moisture stress occurs (FAO-56 Table 22).

    Returns
    -------
    SoilWaterStatus
        Structured results including TAW, RAW, depletion, stress index, and status flags.
    """
    fc = max(0.1, field_capacity_pct)
    wp = max(0.0, min(wilting_point_pct, fc - 0.1))
    theta = max(0.0, moisture_pct)
    zr = max(0.05, root_depth_m)
    p = max(0.1, min(0.8, depletion_fraction_p))

    # 1. Total Available Water (TAW, mm) in root zone: TAW = 1000 * (theta_FC - theta_WP) * Zr
    # Since fc and wp are percentages (0-100), 1000 * (fc - wp)/100 * Zr = 10 * (fc - wp) * Zr
    taw_mm = max(0.0, 10.0 * (fc - wp) * zr)

    # 2. Readily Available Water (RAW, mm): RAW = p * TAW
    raw_mm = p * taw_mm

    # 3. Available Water Percentage (AW%): (theta - wp) / (fc - wp) * 100
    denom = fc - wp
    aw_pct = ((theta - wp) / denom * 100.0) if denom > 0 else 0.0

    # 4. Root zone depletion (Dr, mm): Dr = 1000 * (theta_FC - theta) * Zr
    depletion_mm = max(0.0, 10.0 * (fc - theta) * zr)

    # 5. Over-wet / Over-dry conditions
    # Over-wet: moisture exceeds field capacity by more than 1.0%
    is_over_wet = theta > (fc + 1.0)
    # Over-dry: moisture is at or below permanent wilting point
    is_over_dry = theta <= wp

    # 6. FAO-56 Water stress coefficient Ks (Eq. 84) and Soil Stress Index:
    # If Dr <= RAW (no stress): Ks = 1.0, Stress Index = 0.0
    # If Dr > RAW: Ks = (TAW - Dr) / ((1 - p) * TAW)
    # If Dr >= TAW (theta <= wp): Ks = 0.0, Stress Index = 1.0
    if taw_mm <= 0.0:
        ks = 1.0
        stress_index = 0.0
    elif depletion_mm <= raw_mm:
        ks = 1.0
        stress_index = 0.0
    elif depletion_mm >= taw_mm:
        ks = 0.0
        stress_index = 1.0
    else:
        ks = (taw_mm - depletion_mm) / ((1.0 - p) * taw_mm)
        ks = max(0.0, min(1.0, ks))
        stress_index = 1.0 - ks

    # 7. Condition Label
    if is_over_wet:
        condition_label = "SATURATED / OVER-WET"
    elif is_over_dry:
        condition_label = "SEVERE WILTING / DESICCATED"
    elif stress_index > 0.5:
        condition_label = "HIGH MOISTURE STRESS"
    elif stress_index > 0.0:
        condition_label = "MODERATE MOISTURE STRESS"
    elif theta >= fc - 2.0:
        condition_label = "OPTIMAL / NEAR FIELD CAPACITY"
    else:
        condition_label = "ADEQUATE MOISTURE"

    return SoilWaterStatus(
        volumetric_moisture_pct=round(theta, 2),
        field_capacity_pct=round(fc, 2),
        wilting_point_pct=round(wp, 2),
        root_depth_m=round(zr, 3),
        depletion_fraction_p=round(p, 2),
        taw_mm=round(taw_mm, 2),
        raw_mm=round(raw_mm, 2),
        depletion_mm=round(depletion_mm, 2),
        available_water_pct=round(aw_pct, 2),
        ks=round(ks, 3),
        soil_stress_index=round(stress_index, 3),
        is_over_wet=is_over_wet,
        is_over_dry=is_over_dry,
        condition_label=condition_label,
    )

