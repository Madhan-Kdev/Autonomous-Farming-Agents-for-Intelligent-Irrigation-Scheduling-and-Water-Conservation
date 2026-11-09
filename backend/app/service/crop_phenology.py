"""
Crop Phenology & FAO-56 Crop Coefficient (Kc) Interpolation.

Implements FAO-56 dual and single crop coefficient calculations:
- Determination of crop growth stage (Initial, Development, Mid-Season, Late-Season, Harvest)
- Linear interpolation of crop coefficient Kc along the FAO-56 seasonal curve
- Dynamic root depth Zr progression
- Crop evapotranspiration ETc = Kc * ET0
- Water demand categorization

Reference:
    Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998).
    Crop evapotranspiration — Guidelines for computing crop water
    requirements. FAO Irrigation and Drainage Paper 56, Chapter 6.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CropGrowthStatus:
    """Calculated crop growth stage, Kc coefficient, and water demand."""

    stage_name: str
    days_after_planting: int
    current_kc: float
    current_root_depth_m: float
    etc_mm: float
    water_demand_category: str
    crop_condition_label: str


def determine_growth_stage_and_kc(
    days_after_planting: int,
    days_initial: int,
    days_development: int,
    days_mid: int,
    days_late: int,
    kc_initial: float,
    kc_mid: float,
    kc_end: float,
    root_depth_initial_m: float = 0.15,
    root_depth_max_m: float = 1.0,
    et0_mm: float = 4.0,
    soil_stress_index: float = 0.0,
) -> CropGrowthStatus:
    """
    Calculate current FAO-56 growth stage, interpolated Kc, root depth, and ETc.

    Parameters
    ----------
    days_after_planting : int
        Days elapsed since planting / sowing.
    days_initial, days_development, days_mid, days_late : int
        Length of the 4 FAO-56 stages in days.
    kc_initial, kc_mid, kc_end : float
        Crop coefficients for initial, mid-season peak, and end stages.
    root_depth_initial_m, root_depth_max_m : float
        Initial and maximum rooting depths in meters.
    et0_mm : float
        Reference evapotranspiration (ET0) in mm/day.
    soil_stress_index : float
        Water stress index from soil moisture (0.0 = no stress, 1.0 = wilting).

    Returns
    -------
    CropGrowthStatus
        Interpolated stage name, Kc, root depth, ETc, and demand category.
    """
    t = max(0, days_after_planting)
    l_ini = max(1, days_initial)
    l_dev = max(1, days_development)
    l_mid = max(1, days_mid)
    l_late = max(1, days_late)

    cum_ini = l_ini
    cum_dev = cum_ini + l_dev
    cum_mid = cum_dev + l_mid
    cum_late = cum_mid + l_late

    # 1. Determine Stage and Interpolate Kc & Root Depth (FAO-56 Chapter 6)
    if t <= cum_ini:
        stage_name = "initial"
        current_kc = kc_initial
        current_root_depth_m = root_depth_initial_m
    elif t <= cum_dev:
        stage_name = "development"
        # Linear progression from Kc_ini to Kc_mid
        fraction = (t - cum_ini) / l_dev
        current_kc = kc_initial + fraction * (kc_mid - kc_initial)
        # Linear expansion of root depth
        current_root_depth_m = (
            root_depth_initial_m + fraction * (root_depth_max_m - root_depth_initial_m)
        )
    elif t <= cum_mid:
        stage_name = "mid"
        current_kc = kc_mid
        current_root_depth_m = root_depth_max_m
    elif t <= cum_late:
        stage_name = "late"
        # Linear decline from Kc_mid to Kc_end
        fraction = (t - cum_mid) / l_late
        current_kc = kc_mid + fraction * (kc_end - kc_mid)
        current_root_depth_m = root_depth_max_m
    else:
        stage_name = "harvest"
        current_kc = kc_end
        current_root_depth_m = root_depth_max_m

    # 2. Crop Evapotranspiration ETc = Kc * ET0
    etc_mm = max(0.0, current_kc * max(0.0, et0_mm))

    # 3. Water Demand Category
    if etc_mm >= 6.0:
        water_demand_category = "VERY_HIGH"
    elif etc_mm >= 4.5:
        water_demand_category = "HIGH"
    elif etc_mm >= 3.0:
        water_demand_category = "MODERATE"
    elif etc_mm >= 1.5:
        water_demand_category = "LOW"
    else:
        water_demand_category = "VERY_LOW"

    # 4. Condition Label
    if soil_stress_index > 0.6:
        condition_label = f"SEVERE_STRESS_{stage_name.upper()}"
    elif soil_stress_index > 0.2:
        condition_label = f"MODERATE_STRESS_{stage_name.upper()}"
    else:
        condition_label = f"HEALTHY_{stage_name.upper()}"

    return CropGrowthStatus(
        stage_name=stage_name,
        days_after_planting=t,
        current_kc=round(current_kc, 3),
        current_root_depth_m=round(current_root_depth_m, 3),
        etc_mm=round(etc_mm, 2),
        water_demand_category=water_demand_category,
        crop_condition_label=condition_label,
    )

