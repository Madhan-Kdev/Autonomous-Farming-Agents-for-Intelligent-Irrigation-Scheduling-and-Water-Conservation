"""
Analytics API Endpoints — Water Conservation Summary Board.

Provides:
- GET /api/v1/analytics/conservation-summary
    Aggregates IrrigationRecord data for a farm over a rolling window and
    returns water-use metrics, conservation performance, and a daily trend
    series suitable for a frontend summary board.

All numerical outputs are derived from persisted IrrigationRecord rows —
no LLM-generated figures, no hardcoded estimates.

Metric definitions
------------------
- total_water_applied_mm        : Sum of actual_volume_mm for applied records.
- total_etc_demand_mm           : Sum of etc_on_day_mm — the theoretical crop
                                  water requirement (ETc) over the window.
- total_precipitation_mm        : Sum of precipitation_on_day_mm — observed or
                                  simulated rainfall captured in records.
- irrigation_water_use_efficiency (IWUE) : ETc / applied_water.  A value of 1.0
                                  means every mm applied met exactly one mm of
                                  crop demand.  Values > 1 indicate rain assisted;
                                  values < 1 indicate over-irrigation.
- conventional_water_applied_mm : Model of a fixed-interval conventional system
                                  that irrigates at a configurable fixed depth
                                  (default 6 mm/day) every day regardless of
                                  soil status.
- water_saved_mm                : conventional_water_applied_mm - total_water_applied_mm.
- water_saved_pct               : (saved / conventional) × 100.  Clamped to [0, 100].
  NOTE: This is a model-based estimate, not an experimentally verified figure.

Water-savings formula (FAO-based comparison methodology):
  WS(%) = ((C_w - I_w) / C_w) × 100
  Where:
    C_w = conventional daily fixed application × days with active records
    I_w = intelligent system actual water applied
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.models.irrigation import IrrigationRecord
from app.models.farm import Farm
from app.schemas.common import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DailyConservationPoint(BaseModel):
    """Single-day aggregated water use data point for the trend chart."""

    date: str = Field(..., description="ISO date string YYYY-MM-DD")
    water_applied_mm: float = Field(0.0, description="Intelligent system water applied (mm)")
    etc_demand_mm: float = Field(0.0, description="Crop ETc demand on this day (mm)")
    precipitation_mm: float = Field(0.0, description="Precipitation on this day (mm)")
    conventional_mm: float = Field(
        0.0,
        description="Modelled conventional fixed-interval irrigation (mm) — simulated estimate only",
    )
    saved_mm: float = Field(0.0, description="Estimated mm saved vs conventional (simulated)")
    decisions: list[str] = Field(default_factory=list, description="Decisions made on this day")


class ConservationSummary(BaseModel):
    """
    Water conservation performance summary for a farm over a rolling window.

    IMPORTANT — All savings figures are model-based estimates using a
    configurable fixed-interval conventional baseline.  They do not represent
    experimentally verified or field-measured water savings.
    """

    farm_id: int
    farm_name: str
    window_days: int
    window_start: str
    window_end: str

    # Actual intelligent-system metrics
    total_water_applied_mm: float = Field(
        ..., description="Total water applied by the intelligent system (mm)"
    )
    total_water_applied_liters: float = Field(
        ..., description="Total water applied in liters (mm × area_ha × 10,000)"
    )
    total_etc_demand_mm: float = Field(
        ..., description="Total crop ETc demand over the window (mm)"
    )
    total_precipitation_mm: float = Field(
        ..., description="Total captured precipitation over the window (mm)"
    )

    # Decision breakdown
    total_decisions: int
    decisions_required: int
    decisions_postponed: int
    decisions_not_required: int
    decisions_manual: int

    # Efficiency
    iwue: float = Field(
        ...,
        description=(
            "Irrigation Water Use Efficiency = ETc / water_applied. "
            "Values > 1 indicate rain assisted; < 1 indicate over-irrigation."
        ),
    )
    average_confidence: float = Field(
        ..., description="Average agent confidence score [0, 1] across decisions"
    )

    # Conservation estimate (model-based, conventional baseline)
    conventional_daily_mm: float = Field(
        ...,
        description="Conventional baseline fixed daily application (mm/day) — configurable",
    )
    conventional_total_mm: float = Field(
        ...,
        description=(
            "Modelled conventional system total water over window (mm) — simulated estimate only"
        ),
    )
    water_saved_mm: float = Field(
        ..., description="Estimated water saved vs conventional baseline (mm) — simulated"
    )
    water_saved_pct: float = Field(
        ..., description="Estimated % water saved vs conventional baseline — simulated"
    )
    water_saved_liters: float = Field(
        ...,
        description="Estimated liters saved vs conventional baseline — simulated",
    )

    # Trend data for chart
    daily_trend: list[DailyConservationPoint]

    # Disclaimer
    disclaimer: str = Field(
        default=(
            "SIMULATED MODEL-BASED ESTIMATE: Water savings are computed by comparing "
            "the intelligent system's actual applied volume against a fixed-interval "
            "conventional irrigation baseline. This does not represent experimentally "
            "measured or verified real-world field savings."
        )
    )


# ---------------------------------------------------------------------------
# Helper: total farm area
# ---------------------------------------------------------------------------


def _total_farm_area_ha(farm: Farm) -> float:
    """Return sum of all zone areas in hectares across the farm."""
    total = 0.0
    for field in farm.fields:
        for zone in field.zones:
            total += zone.area_ha or 0.0
    return max(total, 0.001)  # prevent zero division


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/conservation-summary",
    response_model=APIResponse[ConservationSummary],
    summary="Water Conservation Summary Board",
    description=(
        "Aggregates irrigation records for a farm over a rolling window and returns "
        "water-use metrics, Irrigation Water Use Efficiency (IWUE), and an estimated "
        "comparison against a conventional fixed-interval irrigation baseline. "
        "All savings figures are model-based estimates."
    ),
)
def get_conservation_summary(
    farm_id: int = Query(..., description="Farm ID to summarise"),
    days: int = Query(
        default=14,
        ge=1,
        le=365,
        description="Rolling window in days (default 14, max 365)",
    ),
    conventional_daily_mm: float = Query(
        default=6.0,
        ge=1.0,
        le=50.0,
        description=(
            "Conventional baseline fixed daily irrigation depth in mm "
            "(default 6 mm/day — a typical surface/flood irrigation schedule). "
            "Adjust to represent the local conventional practice."
        ),
    ),
    db: Session = Depends(get_db),
) -> APIResponse[ConservationSummary]:
    """Return water conservation summary for the given farm over `days` days."""

    # --- Validate farm exists ---
    farm = db.get(Farm, farm_id)
    if farm is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Farm {farm_id} not found.",
        )

    total_area_ha = _total_farm_area_ha(farm)

    # --- Query window ---
    window_end_dt = datetime.now(timezone.utc)
    window_start_dt = window_end_dt - timedelta(days=days)

    stmt = (
        select(IrrigationRecord)
        .where(IrrigationRecord.farm_id == farm_id)
        .where(IrrigationRecord.scheduled_at >= window_start_dt)
        .order_by(IrrigationRecord.scheduled_at.asc())
    )
    records: list[IrrigationRecord] = list(db.execute(stmt).scalars().all())

    # --- Aggregate by calendar date ---
    by_date: dict[date, list[IrrigationRecord]] = defaultdict(list)
    for rec in records:
        rec_date = rec.scheduled_at.date()
        by_date[rec_date].append(rec)

    # Collect all calendar dates in window (even with no records)
    all_dates: list[date] = []
    cur = window_start_dt.date()
    end_date = window_end_dt.date()
    while cur <= end_date:
        all_dates.append(cur)
        cur += timedelta(days=1)

    # --- Summary accumulators ---
    total_applied_mm = 0.0
    total_etc_mm = 0.0
    total_precip_mm = 0.0
    n_required = 0
    n_postponed = 0
    n_not_required = 0
    n_manual = 0
    confidence_sum = 0.0
    confidence_count = 0

    daily_points: list[DailyConservationPoint] = []

    for d in all_dates:
        day_records = by_date.get(d, [])

        day_applied = sum(
            (r.actual_volume_mm or 0.0)
            for r in day_records
            if r.was_applied
        )
        # Use first ETc and precipitation for the day (they should be consistent
        # across records on the same day since they come from the same weather reading)
        day_etc = max(
            (r.etc_on_day_mm or 0.0 for r in day_records), default=0.0
        )
        day_precip = max(
            (r.precipitation_on_day_mm or 0.0 for r in day_records), default=0.0
        )

        total_applied_mm += day_applied
        total_etc_mm += day_etc
        total_precip_mm += day_precip

        for r in day_records:
            dec = (r.decision or "").upper()
            if dec == "REQUIRED":
                n_required += 1
            elif dec == "POSTPONED":
                n_postponed += 1
            elif dec == "NOT_REQUIRED":
                n_not_required += 1
            elif dec in ("MANUAL_COMMAND", "MANUAL"):
                n_manual += 1

            if r.decision_confidence is not None:
                confidence_sum += r.decision_confidence
                confidence_count += 1

        # Conventional model: irrigates every day at fixed_mm regardless
        # but only on days where the system had active records (or all days)
        conv_day = conventional_daily_mm

        saved_day = max(conv_day - day_applied, 0.0)

        daily_points.append(
            DailyConservationPoint(
                date=d.isoformat(),
                water_applied_mm=round(day_applied, 2),
                etc_demand_mm=round(day_etc, 2),
                precipitation_mm=round(day_precip, 2),
                conventional_mm=round(conv_day, 2),
                saved_mm=round(saved_day, 2),
                decisions=list({(r.decision or "UNKNOWN") for r in day_records}),
            )
        )

    # --- Summary calculations ---
    total_days = len(all_dates)
    conventional_total_mm = conventional_daily_mm * total_days

    # Water savings: (Conventional - Intelligent) / Conventional × 100
    # Safe division; clamp to [0, 100]
    if conventional_total_mm > 0.0:
        raw_saved_mm = max(conventional_total_mm - total_applied_mm, 0.0)
        water_saved_pct = min(
            (raw_saved_mm / conventional_total_mm) * 100.0, 100.0
        )
    else:
        raw_saved_mm = 0.0
        water_saved_pct = 0.0

    # IWUE = ETc / water_applied; guard zero division
    if total_applied_mm > 0.001:
        iwue = round(total_etc_mm / total_applied_mm, 3)
    else:
        iwue = 0.0

    # Volume in liters (mm × area_ha × 10,000)
    applied_liters = total_applied_mm * total_area_ha * 10_000
    saved_liters = raw_saved_mm * total_area_ha * 10_000

    avg_confidence = round(
        confidence_sum / confidence_count if confidence_count > 0 else 0.0, 3
    )

    total_decisions = len(records)

    summary = ConservationSummary(
        farm_id=farm_id,
        farm_name=farm.name,
        window_days=days,
        window_start=window_start_dt.date().isoformat(),
        window_end=end_date.isoformat(),
        total_water_applied_mm=round(total_applied_mm, 2),
        total_water_applied_liters=round(applied_liters, 0),
        total_etc_demand_mm=round(total_etc_mm, 2),
        total_precipitation_mm=round(total_precip_mm, 2),
        total_decisions=total_decisions,
        decisions_required=n_required,
        decisions_postponed=n_postponed,
        decisions_not_required=n_not_required,
        decisions_manual=n_manual,
        iwue=iwue,
        average_confidence=avg_confidence,
        conventional_daily_mm=conventional_daily_mm,
        conventional_total_mm=round(conventional_total_mm, 2),
        water_saved_mm=round(raw_saved_mm, 2),
        water_saved_pct=round(water_saved_pct, 1),
        water_saved_liters=round(saved_liters, 0),
        daily_trend=daily_points,
    )

    return APIResponse(
        success=True,
        data=summary,
        message=f"Water conservation summary for farm {farm_id} over {days} days.",
    )

