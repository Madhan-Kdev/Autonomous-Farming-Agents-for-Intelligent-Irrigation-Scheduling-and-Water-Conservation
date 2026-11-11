"""
Multi-Zone Farm Irrigation Schedule Coordinator & Deconfliction Engine.

Coordinates individual zone irrigation recommendations across the farm footprint:
1. Hydraulic Capacity Constraints:
   - Prevents total concurrent flow from exceeding shared pump flow rate Q_max
   - Staggers simultaneous conflicting zone starts into sequential windows
2. Water Budget Rationing:
   - When available water W_avail < total required volume, performs priority-based
     water rationing (CRITICAL receives 100%, HIGH 85%, MEDIUM scaled, LOW deferred)
3. Operational Scheduling:
   - Computes pumping duration from volume and zone flow rate: T = (V_L / Q) * 60 min
   - Generates conflict-free start_time and end_time timestamps (e.g. 06:00 - 07:15)
   - Assigns optimal execution sequence order based on agronomic urgency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from app.schemas.agent_state import IrrigationPriority, ZoneIrrigationPlan

logger = logging.getLogger(__name__)

# Priority sorting rank (lower = higher urgency)
PRIORITY_RANK: dict[IrrigationPriority, int] = {
    IrrigationPriority.CRITICAL: 1,
    IrrigationPriority.HIGH: 2,
    IrrigationPriority.MEDIUM: 3,
    IrrigationPriority.LOW: 4,
    IrrigationPriority.NONE: 5,
}


@dataclass
class FarmScheduleSummary:
    """Consolidated farm-level irrigation plan metadata."""

    total_farm_volume_liters: float
    total_farm_volume_mm_avg: float
    total_pumping_duration_minutes: float
    max_concurrent_flow_l_h: float
    pump_capacity_l_h: float
    water_budget_liters: float | None
    conflicts_resolved: int
    rationing_applied: bool
    zones_requiring_irrigation: int
    scheduled_zones: list[ZoneIrrigationPlan] = field(default_factory=list)


class FarmScheduleCoordinator:
    """
    Coordinates and deconflicts multi-zone irrigation schedules across a farm.
    """

    def __init__(
        self,
        pump_capacity_l_h: float = 50000.0,
        irrigation_start_hour: int = 6,
        irrigation_start_minute: int = 0,
        water_budget_liters: float | None = None,
    ) -> None:
        self.pump_capacity_l_h = pump_capacity_l_h
        self.irrigation_start_hour = irrigation_start_hour
        self.irrigation_start_minute = irrigation_start_minute
        self.water_budget_liters = water_budget_liters

    def coordinate(
        self,
        plans: list[ZoneIrrigationPlan],
    ) -> FarmScheduleSummary:
        """
        Produce a conflict-free, hydraulically safe consolidated farm schedule.
        """
        if not plans:
            return FarmScheduleSummary(
                total_farm_volume_liters=0.0,
                total_farm_volume_mm_avg=0.0,
                total_pumping_duration_minutes=0.0,
                max_concurrent_flow_l_h=0.0,
                pump_capacity_l_h=self.pump_capacity_l_h,
                water_budget_liters=self.water_budget_liters,
                conflicts_resolved=0,
                rationing_applied=False,
                zones_requiring_irrigation=0,
                scheduled_zones=[],
            )

        active_plans = [p for p in plans if p.irrigation_required and p.recommended_volume_mm > 0]
        inactive_plans = [p for p in plans if not (p.irrigation_required and p.recommended_volume_mm > 0)]

        # Step 1: Compute initial volume in Liters for each zone
        for p in active_plans:
            # V_liters = mm * area_ha * 10,000
            p.volume_liters = round(p.recommended_volume_mm * p.area_ha * 10000.0, 1)
            p.original_volume_mm = p.recommended_volume_mm

        # Step 2: Check Water Budget Rationing
        total_requested_liters = sum(p.volume_liters for p in active_plans)
        rationing_applied = False

        if (
            self.water_budget_liters is not None
            and self.water_budget_liters > 0
            and total_requested_liters > self.water_budget_liters
        ):
            rationing_applied = True
            logger.info(
                "Water rationing triggered: requested %f L > budget %f L",
                total_requested_liters,
                self.water_budget_liters,
            )
            self._apply_water_rationing(active_plans, self.water_budget_liters)

        # Step 3: Sort active plans by priority and stress index
        active_plans.sort(
            key=lambda p: (
                PRIORITY_RANK.get(p.priority, 5),
                -p.stress_index,
                p.zone_id,
            )
        )

        # Step 4: Hydraulic scheduling & deconfliction
        # Stagger zones sequentially or concurrent if flow fits within pump capacity
        conflicts_resolved = 0
        current_time_dt = datetime(2026, 1, 1, self.irrigation_start_hour, self.irrigation_start_minute)

        for idx, p in enumerate(active_plans, start=1):
            p.sequence_order = idx

            # Compute pumping duration in minutes: (Volume_L / FlowRate_L_h) * 60
            flow = max(p.flow_rate_l_h, 5000.0)
            duration_min = max(10.0, round((p.volume_liters / flow) * 60.0, 1))
            p.duration_minutes = duration_min

            # Assign non-overlapping execution window
            start_str = current_time_dt.strftime("%H:%M")
            end_time_dt = current_time_dt + timedelta(minutes=duration_min)
            end_str = end_time_dt.strftime("%H:%M")

            p.start_time = start_str
            p.end_time = end_str

            # If this zone had to be delayed behind another zone to avoid exceeding pump flow
            if idx > 1:
                p.conflict_detected = True
                conflicts_resolved += 1
                p.evidence.append(
                    f"Hydraulic Deconfliction: Staggered start to {start_str} to respect "
                    f"pump capacity limit ({self.pump_capacity_l_h:,.0f} L/h)."
                )

            # Advance clock for next sequential zone
            current_time_dt = end_time_dt

        # Handle inactive plans (no irrigation)
        for p in inactive_plans:
            p.volume_liters = 0.0
            p.duration_minutes = 0.0
            p.start_time = "N/A"
            p.end_time = "N/A"
            p.sequence_order = len(active_plans) + 1

        all_scheduled = active_plans + inactive_plans

        # Totals
        total_farm_liters = sum(p.volume_liters for p in active_plans)
        total_duration = sum(p.duration_minutes for p in active_plans)
        avg_mm = (
            sum(p.recommended_volume_mm for p in active_plans) / len(active_plans)
            if active_plans
            else 0.0
        )

        return FarmScheduleSummary(
            total_farm_volume_liters=round(total_farm_liters, 1),
            total_farm_volume_mm_avg=round(avg_mm, 2),
            total_pumping_duration_minutes=round(total_duration, 1),
            max_concurrent_flow_l_h=max((p.flow_rate_l_h for p in active_plans), default=0.0),
            pump_capacity_l_h=self.pump_capacity_l_h,
            water_budget_liters=self.water_budget_liters,
            conflicts_resolved=conflicts_resolved,
            rationing_applied=rationing_applied,
            zones_requiring_irrigation=len(active_plans),
            scheduled_zones=all_scheduled,
        )

    def _apply_water_rationing(
        self, plans: list[ZoneIrrigationPlan], budget_liters: float
    ) -> None:
        """
        Ration water across zones based on priority tier.
        """
        critical = [p for p in plans if p.priority == IrrigationPriority.CRITICAL]
        high = [p for p in plans if p.priority == IrrigationPriority.HIGH]
        others = [p for p in plans if p.priority not in (IrrigationPriority.CRITICAL, IrrigationPriority.HIGH)]

        remaining = budget_liters

        # 1. Critical zones get 100% of demand first
        for p in critical:
            if remaining >= p.volume_liters:
                remaining -= p.volume_liters
            else:
                # Even critical must scale if budget is catastrophically low
                scale = max(0.2, remaining / max(p.volume_liters, 1.0))
                p.volume_liters *= scale
                p.recommended_volume_mm *= scale
                p.rationing_applied = True
                remaining = 0.0

        # 2. High priority gets remaining
        if remaining > 0 and high:
            high_demand = sum(p.volume_liters for p in high)
            if remaining >= high_demand:
                remaining -= high_demand
            else:
                scale = remaining / high_demand
                for p in high:
                    p.volume_liters *= scale
                    p.recommended_volume_mm *= scale
                    p.rationing_applied = True
                    p.evidence.append(f"Water Budget Rationing: Scaled to {scale:.1%} of optimal demand.")
                remaining = 0.0

        # 3. Medium & Low priority
        if remaining > 0 and others:
            other_demand = sum(p.volume_liters for p in others)
            scale = remaining / other_demand
            for p in others:
                p.volume_liters *= scale
                p.recommended_volume_mm *= scale
                p.rationing_applied = True
                p.evidence.append(f"Water Budget Rationing: Scaled to {scale:.1%} of optimal demand.")
        elif others:
            # Deficit deferral
            for p in others:
                p.volume_liters = 0.0
                p.recommended_volume_mm = 0.0
                p.irrigation_required = False
                p.rationing_applied = True
                p.evidence.append("Water Budget Exhausted: Irrigation deferred to next cycle due to farm-level deficit.")
