"""
Crop Intelligence Agent.

Responsibilities
----------------
1. Resolve active crop and growth stage for the targeted zone.
2. Determine days after planting (DAP) and interpolate FAO-56 crop coefficient (Kc).
3. Track dynamic root depth expansion (Zr).
4. Compute crop water requirement (ETc = Kc * ET0) and demand category.
5. Correlate with soil stress index to evaluate overall crop water condition.
6. Populate ``state.crop`` in the shared AgentState and update ``state.et0.etc_mm``.

ARCHITECTURAL CONSTRAINT (from project spec):
    This agent writes ONLY to the ``crop`` section of AgentState (and updates
    the derived etc_mm field in ``et0``).
    ALL crop coefficients and stage durations come from validated FAO-56 tables.
    LLMs are NEVER used to hallucinate crop coefficients or numerical values.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base.agent_types import AgentType
from app.agents.base.base_agent import BaseAgent
from app.models.crop import Crop
from app.models.zone import Zone
from app.repositories.repositories import (
    CropGrowthStageRepository,
    CropRepository,
    FarmRepository,
    FieldRepository,
    ZoneRepository,
)
from app.schemas.agent_state import AgentState, CropContext
from app.service.crop_phenology import determine_growth_stage_and_kc

logger = logging.getLogger(__name__)


class CropAgent(BaseAgent):
    """
    Crop Intelligence Agent.

    Interpolates FAO-56 crop coefficients and computes crop water requirements.

    Writes to
    ---------
    * ``state.crop`` — CropContext
    * ``state.et0.etc_mm`` — Float (updated with ETc = Kc * ET0)

    Configuration keys
    ------------------
    ``db`` : SQLAlchemy Session (required)
    ``default_dap`` : int — default days after planting if not recorded (default: 45)
    """

    name = AgentType.CROP.value
    timeout_seconds = 30.0

    def __init__(self, db: Session, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._db = db
        self._default_dap: int = self.config.get("default_dap", 45)
        self._crop_repo = CropRepository(db)
        self._stage_repo = CropGrowthStageRepository(db)
        self._zone_repo = ZoneRepository(db)
        self._field_repo = FieldRepository(db)
        self._farm_repo = FarmRepository(db)

    # ------------------------------------------------------------------ #
    # Core agent logic
    # ------------------------------------------------------------------ #

    def _run(self, state: AgentState) -> AgentState:
        """
        Execute crop intelligence pipeline.

        Steps:
        1. Resolve target zone and crop species.
        2. Query validated agronomic constants (Kc_ini, Kc_mid, Kc_end, stage lengths).
        3. Resolve days after planting (DAP).
        4. Interpolate Kc and root depth using FAO-56 curves.
        5. Calculate crop evapotranspiration (ETc = Kc * ET0).
        6. Persist or update CropGrowthStage record.
        7. Populate state.crop and state.et0.etc_mm.
        """
        zone = self._resolve_target_zone(state)
        crop_name = self._resolve_crop_name(state, zone)

        if not crop_name:
            self._add_warning(state, "No crop specified or found for target zone.")
            state.crop = self._empty_crop("no_crop_specified")
            return state

        crop = self._crop_repo.get_by_name(crop_name)
        is_fallback = False

        if crop is None:
            self._add_warning(
                state, f"Crop '{crop_name}' not in FAO-56 database; using Wheat default profile."
            )
            crop = self._crop_repo.get_by_name("Wheat")
            is_fallback = True

        if crop is None:
            self._add_warning(state, "No agronomic crop reference data available.")
            state.crop = self._empty_crop("no_agronomic_reference_data")
            return state

        self._log_info("CropAgent: analyzing crop '%s' for Zone id=%s", crop.name, zone.id if zone else "N/A")

        # Step 3: Determine Days After Planting (DAP)
        dap, planting_date = self._resolve_dap(state, zone)
        if state.request and state.request.override_growth_stage:
            stage_req = state.request.override_growth_stage.lower().strip()
            if "ini" in stage_req:
                dap = max(1, crop.days_initial // 2)
            elif "dev" in stage_req:
                dap = crop.days_initial + max(1, crop.days_development // 2)
            elif "mid" in stage_req:
                dap = crop.days_initial + crop.days_development + max(1, crop.days_mid // 2)
            elif "late" in stage_req or "end" in stage_req:
                dap = crop.days_initial + crop.days_development + crop.days_mid + max(1, crop.days_late // 2)

        # Step 4: Extract reference ET0 and soil stress from state
        et0_mm = 4.0  # standard fallback
        if state.et0 and state.et0.et0_reference_mm is not None:
            et0_mm = state.et0.et0_reference_mm

        soil_stress = 0.0
        if state.soil and state.soil.soil_stress_index is not None:
            soil_stress = state.soil.soil_stress_index

        # Step 5: Compute growth stage and interpolated Kc
        status = determine_growth_stage_and_kc(
            days_after_planting=dap,
            days_initial=crop.days_initial,
            days_development=crop.days_development,
            days_mid=crop.days_mid,
            days_late=crop.days_late,
            kc_initial=crop.kc_initial,
            kc_mid=crop.kc_mid,
            kc_end=crop.kc_end,
            root_depth_initial_m=crop.root_depth_initial_m,
            root_depth_max_m=crop.root_depth_max_m,
            et0_mm=et0_mm,
            soil_stress_index=soil_stress,
        )

        # Step 6: Persist/update CropGrowthStage if zone exists
        if zone:
            self._sync_growth_stage(zone.id, crop.id, status, planting_date)

        # Step 7: Build evidence and context
        evidence = [
            f"Crop Species: {crop.name} ({crop.crop_type or 'General'})",
            f"Reference: {crop.reference or 'FAO-56 Table 12'}",
            f"Days After Planting: {status.days_after_planting} days",
            f"Growth Stage: {status.stage_name.upper()} (lengths: ini={crop.days_initial}d, dev={crop.days_development}d, mid={crop.days_mid}d, late={crop.days_late}d)",
            f"Interpolated Crop Coefficient (Kc): {status.current_kc:.3f}",
            f"Effective Root Depth (Zr): {status.current_root_depth_m:.2f} m (max {crop.root_depth_max_m:.2f} m)",
            f"Reference Evapotranspiration (ET0): {et0_mm:.2f} mm/day",
            f"Crop Water Requirement (ETc = Kc * ET0): {status.etc_mm:.2f} mm/day",
            f"Water Demand Category: {status.water_demand_category}",
            f"Crop Condition: {status.crop_condition_label}",
        ]

        if soil_stress > 0.0:
            adjusted_etc = round(status.etc_mm * (1.0 - soil_stress), 2)
            evidence.append(
                f"Soil Moisture Stress detected ({soil_stress:.2f}) -> Adjusted ETc_adj: {adjusted_etc:.2f} mm/day"
            )

        confidence = 0.95 if not is_fallback else 0.70

        state.crop = CropContext(
            crop_type=crop.name,
            growth_stage=status.stage_name,
            crop_coefficient_kc=status.current_kc,
            root_depth_m=status.current_root_depth_m,
            crop_water_requirement_mm=status.etc_mm,
            crop_stress_index=soil_stress,
            water_demand_category=status.water_demand_category,
            crop_condition=status.crop_condition_label,
            confidence=confidence,
            evidence=evidence,
        )

        # Also update etc_mm in state.et0 if state.et0 is available
        if state.et0:
            state.et0.etc_mm = status.etc_mm
            state.et0.evidence.append(f"ETc computed by CropAgent: {status.etc_mm:.2f} mm/day (Kc={status.current_kc:.3f})")

        self._log_info(
            "CropAgent: completed analysis — Crop=%s, Stage=%s, Kc=%.3f, ETc=%.2f mm/day, Demand=%s",
            crop.name,
            status.stage_name,
            status.current_kc,
            status.etc_mm,
            status.water_demand_category,
        )
        return state

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #

    def _resolve_target_zone(self, state: AgentState) -> Zone | None:
        """Find the relevant zone from request."""
        req = state.request
        if not req:
            return None

        if req.zone_ids:
            return self._zone_repo.get_by_id(req.zone_ids[0])

        if req.field_id:
            zones = self._zone_repo.get_active_zones(req.field_id)
            return zones[0] if zones else None

        if req.farm_id:
            fields = self._field_repo.get_by_farm(req.farm_id)
            for field in fields:
                zones = self._zone_repo.get_active_zones(field.id)
                if zones:
                    return zones[0]

        return None

    def _resolve_crop_name(self, state: AgentState, zone: Zone | None) -> str | None:
        """Resolve crop name from request or zone."""
        if state.request and state.request.crop_type:
            return state.request.crop_type

        if zone and zone.crop_name:
            return zone.crop_name

        # If neither request nor zone specifies crop, record warning
        self._add_warning(
            state, "No crop_type in request and no crop assigned to target zone; using default crop."
        )
        all_crops = self._crop_repo.get_all_crops()
        return all_crops[0].name if all_crops else None

    def _resolve_dap(self, state: AgentState, zone: Zone | None) -> tuple[int, date]:
        """
        Derive Days After Planting (DAP) and planting date.
        """
        target_date = (
            state.request.target_date if (state.request and state.request.target_date) else date.today()
        )

        if zone:
            existing_stage = self._stage_repo.get_current_for_zone(zone.id)
            if existing_stage and existing_stage.planting_date:
                elapsed = (target_date - existing_stage.planting_date).days
                return max(0, elapsed), existing_stage.planting_date

        planting_date = target_date - timedelta(days=self._default_dap)
        return self._default_dap, planting_date

    def _sync_growth_stage(
        self, zone_id: int, crop_id: int, status: Any, planting_date: date
    ) -> None:
        """Persist or update CropGrowthStage record in database."""
        try:
            existing = self._stage_repo.get_current_for_zone(zone_id)
            if existing:
                existing.stage_name = status.stage_name
                existing.days_after_planting = status.days_after_planting
                existing.current_kc = status.current_kc
                existing.current_root_depth_m = status.current_root_depth_m
                self._db.flush()
            else:
                self._stage_repo.create(
                    zone_id=zone_id,
                    crop_id=crop_id,
                    stage_name=status.stage_name,
                    planting_date=planting_date,
                    days_after_planting=status.days_after_planting,
                    current_kc=status.current_kc,
                    current_root_depth_m=status.current_root_depth_m,
                    notes="Auto-created by CropAgent",
                )
        except Exception as exc:
            logger.warning("Could not sync CropGrowthStage record: %s", exc)
            self._db.rollback()

    @staticmethod
    def _empty_crop(reason: str) -> CropContext:
        """Construct empty CropContext on failure."""
        return CropContext(
            crop_type="Unknown",
            growth_stage="Unknown",
            crop_coefficient_kc=None,
            root_depth_m=None,
            crop_water_requirement_mm=None,
            crop_stress_index=0.0,
            water_demand_category="UNKNOWN",
            crop_condition=f"Unavailable: {reason}",
            confidence=0.0,
            evidence=[f"Crop analysis skipped: {reason}"],
        )
