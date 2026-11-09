"""
Historical Irrigation and Weather Analytics Service.

Provides analytical computations for historical patterns:
- 30-day moving average and cumulative rainfall
- 7-day cumulative irrigation depth (mm) and volumetric usage (liters)
- Water balance audit: (Irrigation + Rainfall) vs Cumulative ETc
- Trend detection for historical over-irrigation or under-irrigation
- Seasonal agro-climatic demand classification
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Sequence

logger = logging.getLogger(__name__)


@dataclass
class HistoricalWaterMetrics:
    """Consolidated historical water metrics for a zone."""

    avg_rainfall_30d_mm: float
    total_rainfall_30d_mm: float
    rain_days_30d: int
    avg_irrigation_7d_mm: float
    total_irrigation_7d_mm: float
    water_usage_7d_liters: float
    detected_over_irrigation: bool
    detected_under_irrigation: bool
    seasonal_demand_pattern: str
    water_balance_ratio: float  # (Supply / Demand)


def compute_historical_water_metrics(
    rainfall_records: Sequence[float],
    irrigation_records_7d: Sequence[float],
    zone_area_ha: float = 1.0,
    cumulative_etc_7d: float = 28.0,
    target_date: date | None = None,
    recent_soil_stress_index: float = 0.0,
) -> HistoricalWaterMetrics:
    """
    Compute 30-day rainfall, 7-day irrigation, volume in liters, and over/under-irrigation trends.

    Parameters
    ----------
    rainfall_records : Sequence[float]
        Daily rainfall amounts (mm) over up to 30 days.
    irrigation_records_7d : Sequence[float]
        Daily irrigation applied (mm) over up to 7 days.
    zone_area_ha : float
        Zone area in hectares (used to convert mm to liters).
    cumulative_etc_7d : float
        Cumulative crop evapotranspiration demand over the past 7 days (mm).
    target_date : date | None
        Current date used to determine seasonal pattern.
    recent_soil_stress_index : float
        Current or recent soil moisture stress index (0.0 = none, 1.0 = wilting).

    Returns
    -------
    HistoricalWaterMetrics
    """
    # 1. 30-day Rainfall Analytics
    if rainfall_records:
        total_rain_30d = sum(r for r in rainfall_records if r is not None)
        rain_days_30d = sum(1 for r in rainfall_records if r is not None and r > 0.5)
        avg_rain_30d = total_rain_30d / len(rainfall_records)
    else:
        total_rain_30d = 0.0
        rain_days_30d = 0
        avg_rain_30d = 0.0

    # 2. 7-day Irrigation Analytics
    if irrigation_records_7d:
        total_irrig_7d = sum(i for i in irrigation_records_7d if i is not None)
        avg_irrig_7d = total_irrig_7d / len(irrigation_records_7d)
    else:
        total_irrig_7d = 0.0
        avg_irrig_7d = 0.0

    # 3. Volumetric calculation (Liters):
    # 1 mm depth * 1 m² = 1 Liter
    # 1 ha = 10,000 m²
    # Liters = mm * area_ha * 10,000
    area = max(0.01, zone_area_ha)
    water_usage_liters = round(total_irrig_7d * area * 10000.0, 1)

    # 4. Water Balance Audit & Anomaly Detection
    # Total supply over 7 days = total irrigation applied + recent 7-day rainfall
    recent_rain_7d = sum(rainfall_records[-7:]) if len(rainfall_records) >= 7 else total_rain_30d
    total_supply_7d = total_irrig_7d + recent_rain_7d
    demand_7d = max(1.0, cumulative_etc_7d)

    balance_ratio = total_supply_7d / demand_7d

    # Over-irrigation: Total supply significantly exceeds crop demand (> 140% of ETc)
    detected_over_irrigation = balance_ratio > 1.40 and total_irrig_7d > 10.0

    # Under-irrigation: Total supply is severely below crop demand (< 60% of ETc) AND soil is stressed
    detected_under_irrigation = (balance_ratio < 0.60 and recent_soil_stress_index > 0.3)

    # 5. Seasonal Demand Classification
    now_date = target_date or date.today()
    month = now_date.month

    if month in (3, 4, 5):
        seasonal_pattern = "PRE_MONSOON_SUMMER_PEAK"
    elif month in (6, 7, 8, 9):
        seasonal_pattern = "MONSOON_WET_SEASON"
    elif month in (10, 11):
        seasonal_pattern = "POST_MONSOON_AUTUMN"
    else:
        seasonal_pattern = "WINTER_MODERATE_DEMAND"

    return HistoricalWaterMetrics(
        avg_rainfall_30d_mm=round(avg_rain_30d, 2),
        total_rainfall_30d_mm=round(total_rain_30d, 2),
        rain_days_30d=rain_days_30d,
        avg_irrigation_7d_mm=round(avg_irrig_7d, 2),
        total_irrigation_7d_mm=round(total_irrig_7d, 2),
        water_usage_7d_liters=water_usage_liters,
        detected_over_irrigation=detected_over_irrigation,
        detected_under_irrigation=detected_under_irrigation,
        seasonal_demand_pattern=seasonal_pattern,
        water_balance_ratio=round(balance_ratio, 2),
    )
