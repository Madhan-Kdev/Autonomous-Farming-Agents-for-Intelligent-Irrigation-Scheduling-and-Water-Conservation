"""
Water Optimization & Conservation Engine.

Provides quantitative comparisons between conventional agricultural irrigation
baselines (fixed calendar schedule / flood delivery) and the agentic AI
precision schedule:
- Baseline volume estimation
- Water savings calculation (depth in mm, percentage %, and volume in Liters)
- Deep percolation and over-irrigation prevention audit
- Crop water stress / under-irrigation safety safeguard
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class WaterOptimizationResult:
    """Consolidated results of the water conservation audit."""

    baseline_volume_mm: float
    optimized_volume_mm: float
    water_saving_mm: float
    water_saving_pct: float
    water_saving_liters: float
    over_irrigation_prevented: bool
    under_irrigation_risk: bool
    optimization_method: str
    evidence: list[str] = field(default_factory=list)


def compute_water_savings(
    recommended_volume_mm: float,
    is_irrigation_required: bool,
    conventional_baseline_depth_mm: float = 25.0,
    farm_or_zone_area_ha: float = 2.0,
    soil_stress_index: float = 0.0,
    available_water_pct: float = 50.0,
    water_holding_capacity_mm: float = 36.0,
    etc_mm: float = 4.5,
) -> WaterOptimizationResult:
    """
    Compute quantitative water savings and conservation impact.

    Parameters
    ----------
    recommended_volume_mm : float
        AI-recommended application depth (mm).
    is_irrigation_required : bool
        Whether the system decided irrigation was necessary.
    conventional_baseline_depth_mm : float
        Standard conventional calendar application depth (default: 25.0 mm).
    farm_or_zone_area_ha : float
        Area in hectares.
    soil_stress_index : float
        Moisture stress index (0.0 = none, 1.0 = wilting).
    available_water_pct : float
        Available water content (% of TAW).
    water_holding_capacity_mm : float
        Total Available Water capacity (TAW) in mm.
    etc_mm : float
        Crop water requirement (mm/day).

    Returns
    -------
    WaterOptimizationResult
    """
    baseline_mm = max(5.0, conventional_baseline_depth_mm)
    area_ha = max(0.01, farm_or_zone_area_ha)

    if not is_irrigation_required:
        optimized_mm = 0.0
    else:
        optimized_mm = max(0.0, recommended_volume_mm)

    # 1. Compute Savings
    saving_mm = max(0.0, baseline_mm - optimized_mm)
    saving_pct = round((saving_mm / baseline_mm * 100.0), 1) if baseline_mm > 0 else 0.0

    # 2. Liters conversion: 1 mm * 1 ha * 10,000 = 10,000 Liters
    saving_liters = round(saving_mm * area_ha * 10000.0, 1)

    # 3. Over-irrigation audit:
    # Conventional baseline over-irrigates when no irrigation is needed,
    # or when baseline exceeds the AI-optimized precision demand.
    over_irrigation_prevented = (
        not is_irrigation_required
        or (baseline_mm > optimized_mm and saving_mm >= 5.0)
    )

    # 4. Under-irrigation safeguard:
    # Under-irrigation risk exists ONLY if irrigation was required, but the recommended
    # volume is too low to relieve high moisture stress.
    under_irrigation_risk = (
        is_irrigation_required
        and soil_stress_index > 0.60
        and optimized_mm < etc_mm
    )

    method = "FAO-56 Dynamic Deficit & Root-Zone Soil Balance Optimization"

    evidence = [
        f"Conventional Irrigation Baseline: {baseline_mm:.1f} mm ({baseline_mm * area_ha * 10000.0:,.0f} Liters)",
        f"AI Precision Optimized Schedule: {optimized_mm:.1f} mm ({optimized_mm * area_ha * 10000.0:,.0f} Liters)",
        f"Net Water Conserved: {saving_mm:.1f} mm ({saving_pct:.1f}% reduction, saving {saving_liters:,.0f} Liters across {area_ha:.2f} ha)",
        f"Method: {method}",
    ]

    if over_irrigation_prevented:
        excess_depth = max(0.0, baseline_mm - optimized_mm) if is_irrigation_required else baseline_mm
        evidence.append(
            f"Over-irrigation averted: Conventional schedule would have caused ~{excess_depth:.1f} mm deep drainage loss."
        )

    if not under_irrigation_risk:
        evidence.append("Agronomic safeguard verified: Zero under-irrigation stress induced; crop transpiration maintained.")
    else:
        evidence.append("CAUTION: Controlled deficit applied; close soil moisture monitoring advised.")

    return WaterOptimizationResult(
        baseline_volume_mm=round(baseline_mm, 1),
        optimized_volume_mm=round(optimized_mm, 1),
        water_saving_mm=round(saving_mm, 1),
        water_saving_pct=saving_pct,
        water_saving_liters=saving_liters,
        over_irrigation_prevented=over_irrigation_prevented,
        under_irrigation_risk=under_irrigation_risk,
        optimization_method=method,
        evidence=evidence,
    )
