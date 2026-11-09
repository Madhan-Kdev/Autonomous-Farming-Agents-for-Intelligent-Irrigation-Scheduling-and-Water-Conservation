"""
Water Conservation & Optimization Agent.

Responsibilities
----------------
1. Audit conventional calendar-based irrigation baselines vs AI precision schedules.
2. Quantify net water savings in application depth (mm), percentage (%), and volume (Liters).
3. Detect prevention of deep percolation losses and unnecessary over-irrigation.
4. Verify agricultural safety to prevent under-irrigation crop water stress.
5. Populate ``state.optimization`` in the shared AgentState.

ARCHITECTURAL CONSTRAINT (from project spec):
    This agent writes ONLY to the ``optimization`` section of AgentState.
    ALL water saving quantities and percentages derive from analytical comparisons
    between conventional baselines and optimized schedules — NEVER from LLM hallucinations.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base.agent_types import AgentType
from app.agents.base.base_agent import BaseAgent
from app.models.zone import Zone
from app.repositories.repositories import (
    FarmRepository,
    FieldRepository,
    ZoneRepository,
)
from app.schemas.agent_state import (
    AgentState,
    IrrigationDecision,
    OptimizationContext,
)
from app.service.water_optimization_engine import (
    WaterOptimizationResult,
    compute_water_savings,
)

logger = logging.getLogger(__name__)


class WaterOptimizationAgent(BaseAgent):
    """
    Water Conservation & Optimization Agent.

    Evaluates water savings achieved by dynamic agentic scheduling over
    rigid conventional agricultural irrigation baselines.

    Writes to
    ---------
    * ``state.optimization`` — OptimizationContext

    Configuration keys
    ------------------
    ``db`` : SQLAlchemy Session (required)
    ``conventional_baseline_mm`` : float — standard baseline event depth (default: 25.0 mm)
    """

    name = AgentType.WATER_OPTIMIZATION.value
    timeout_seconds = 30.0

    def __init__(self, db: Session, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._db = db
        self._conventional_baseline_mm: float = self.config.get(
            "conventional_baseline_mm", 25.0
        )
        self._zone_repo = ZoneRepository(db)
        self._field_repo = FieldRepository(db)
        self._farm_repo = FarmRepository(db)

    # ------------------------------------------------------------------ #
    # Core agent logic
    # ------------------------------------------------------------------ #

    def _run(self, state: AgentState) -> AgentState:
        """
        Execute water conservation optimization audit.

        Steps:
        1. Resolve operational footprint (area in ha).
        2. Extract scheduled irrigation volume and requirement status.
        3. Extract soil storage deficit and crop transpiration demand.
        4. Compute water savings and risk metrics.
        5. Populate state.optimization.
        """
        area_ha = self._resolve_operational_area(state)

        # 2. Extract decision details
        dec_ctx = state.irrigation_decision
        is_required = (
            dec_ctx.decision == IrrigationDecision.REQUIRED
            if dec_ctx
            else False
        )
        optimized_volume_mm = (
            dec_ctx.recommended_volume_mm or 0.0
            if dec_ctx and dec_ctx.recommended_volume_mm is not None
            else 0.0
        )

        # Apply water availability constraint if provided
        water_avail_status = state.request.override_water_availability_status if state.request else None
        if state.request and state.request.override_available_water_liters is not None and area_ha > 0:
            max_avail_mm = state.request.override_available_water_liters / (area_ha * 10000.0)
            if optimized_volume_mm > max_avail_mm:
                optimized_volume_mm = round(max(0.0, max_avail_mm), 1)
                if state.irrigation_decision:
                    state.irrigation_decision.recommended_volume_mm = optimized_volume_mm

        # 3. Extract soil and crop parameters
        s = state.soil
        soil_stress = s.soil_stress_index if s else 0.0
        aw_pct = s.available_water_pct if (s and s.available_water_pct is not None) else 50.0
        whc_mm = s.water_holding_capacity_mm or 36.0 if s else 36.0

        c = state.crop
        e = state.et0
        etc_mm = 4.5
        if c and c.crop_water_requirement_mm is not None:
            etc_mm = c.crop_water_requirement_mm
        elif e and e.etc_mm is not None:
            etc_mm = e.etc_mm

        self._log_info(
            "WaterOptimizationAgent: evaluating savings — Baseline=%.1f mm, Optimized=%.1f mm, Area=%.2f ha",
            self._conventional_baseline_mm,
            optimized_volume_mm,
            area_ha,
        )

        # 4. Compute savings
        result: WaterOptimizationResult = compute_water_savings(
            recommended_volume_mm=optimized_volume_mm,
            is_irrigation_required=is_required,
            conventional_baseline_depth_mm=self._conventional_baseline_mm,
            farm_or_zone_area_ha=area_ha,
            soil_stress_index=soil_stress,
            available_water_pct=aw_pct,
            water_holding_capacity_mm=whc_mm,
            etc_mm=etc_mm,
        )

        # 5. Populate state.optimization
        state.optimization = OptimizationContext(
            baseline_volume_mm=result.baseline_volume_mm,
            optimized_volume_mm=result.optimized_volume_mm,
            water_saving_mm=result.water_saving_mm,
            water_saving_pct=result.water_saving_pct,
            over_irrigation_detected=result.over_irrigation_prevented,
            under_irrigation_risk=result.under_irrigation_risk,
            optimization_method=result.optimization_method,
            evidence=result.evidence,
        )

        self._log_info(
            "WaterOptimizationAgent: completed — Saved %.1f mm (%.1f%%, %s Liters), OverIrrigPrevented=%s",
            result.water_saving_mm,
            result.water_saving_pct,
            f"{result.water_saving_liters:,.0f}",
            result.over_irrigation_prevented,
        )
        return state

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #

    def _resolve_operational_area(self, state: AgentState) -> float:
        """Derive total active area in hectares from state."""
        # 1. If zone_plans are populated, sum their areas
        if state.zone_plans:
            total_ha = 0.0
            for zp in state.zone_plans:
                zone = self._zone_repo.get_by_id(zp.zone_id)
                if zone and zone.area_ha:
                    total_ha += zone.area_ha
            if total_ha > 0.0:
                return total_ha

        # 2. If target zone is in request
        req = state.request
        if req and req.zone_ids:
            zone = self._zone_repo.get_by_id(req.zone_ids[0])
            if zone and zone.area_ha:
                return zone.area_ha

        # 3. If field is in request
        if req and req.field_id:
            zones = self._zone_repo.get_active_zones(req.field_id)
            sum_ha = sum(z.area_ha for z in zones if z.area_ha)
            if sum_ha > 0.0:
                return sum_ha

        # 4. If farm is in request
        if req and req.farm_id:
            farm = self._farm_repo.get_by_id(req.farm_id)
            if farm and farm.total_area_ha:
                return farm.total_area_ha

        # 5. Default baseline area
        return 2.0

