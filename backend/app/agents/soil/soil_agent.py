"""
Soil Moisture Intelligence Agent.

Responsibilities
----------------
1. Ingest zone-level soil profile telemetry (simulated software readings).
2. Compute Total Available Water (TAW), Readily Available Water (RAW),
   Available Water Percentage (AW%), and Root Zone Depletion (Dr).
3. Determine FAO-56 soil water stress coefficient (Ks) and soil stress index.
4. Detect over-wet (waterlogged) or over-dry (wilting) conditions.
5. Populate ``state.soil`` in the shared AgentState.

ARCHITECTURAL CONSTRAINT (from project spec):
    This agent writes ONLY to the ``soil`` section of AgentState.
    ALL numerical calculations derive from validated analytical soil physics.
    LLMs are NEVER used to fabricate numerical soil measurements.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base.agent_types import AgentType
from app.agents.base.base_agent import BaseAgent
from app.models.zone import SoilProfile, Zone
from app.repositories.repositories import (
    CropGrowthStageRepository,
    CropRepository,
    FarmRepository,
    FieldRepository,
    SoilProfileRepository,
    ZoneRepository,
)
from app.schemas.agent_state import AgentState, SoilContext
from app.service.soil_physics import (
    SOIL_TEXTURE_DEFAULTS,
    SoilWaterStatus,
    compute_soil_water_status,
)

logger = logging.getLogger(__name__)


class SoilAgent(BaseAgent):
    """
    Soil Moisture Intelligence Agent.

    Evaluates soil moisture levels against physical thresholds (field capacity,
    wilting point) to calculate available water, depletion, and stress indices.

    Writes to
    ---------
    * ``state.soil`` — SoilContext

    Configuration keys
    ------------------
    ``db`` : SQLAlchemy Session (required)
    ``use_fallback_simulation`` : bool — use simulated data if no DB record found
    """

    name = AgentType.SOIL.value
    timeout_seconds = 30.0

    def __init__(self, db: Session, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._db = db
        self._use_fallback: bool = self.config.get("use_fallback_simulation", True)
        self._soil_repo = SoilProfileRepository(db)
        self._zone_repo = ZoneRepository(db)
        self._field_repo = FieldRepository(db)
        self._farm_repo = FarmRepository(db)
        self._crop_repo = CropRepository(db)
        self._stage_repo = CropGrowthStageRepository(db)

    # ------------------------------------------------------------------ #
    # Core agent logic
    # ------------------------------------------------------------------ #

    def _run(self, state: AgentState) -> AgentState:
        """
        Execute soil moisture analysis pipeline.

        Steps:
        1. Resolve target zone from request context.
        2. Fetch latest SoilProfile record for the zone.
        3. Determine effective root depth and depletion fraction p.
        4. Compute soil water balance metrics (TAW, RAW, AW%, Ks, Stress Index).
        5. Populate state.soil with structured SoilContext.
        """
        zone = self._resolve_target_zone(state)
        if zone is None:
            self._add_warning(state, "Target zone could not be resolved for soil analysis.")
            state.soil = self._empty_soil("zone_not_resolved")
            return state

        self._log_info("SoilAgent: analyzing soil moisture for Zone id=%d (%s)", zone.id, zone.name)

        # Step 2: Fetch latest soil profile or fallback simulation
        profile = self._soil_repo.get_latest_for_zone(zone.id)
        is_fallback = False

        if profile is None:
            if self._use_fallback:
                self._add_warning(
                    state,
                    f"No SoilProfile record found for Zone id={zone.id}; using simulated fallback profile.",
                )
                profile = self._generate_simulated_profile(zone)
                is_fallback = True
            else:
                self._add_warning(state, f"No SoilProfile found for Zone id={zone.id}.")
                state.soil = self._empty_soil("no_soil_profile", zone_id=zone.id)
                return state

        # Step 3: Determine root depth and depletion fraction
        root_depth_m, p_fraction, crop_name = self._resolve_crop_parameters(zone)

        # Step 4: Compute analytical soil water status
        fc = profile.field_capacity_pct or 25.0
        wp = profile.wilting_point_pct or 12.0
        moisture = profile.volumetric_moisture_pct if profile.volumetric_moisture_pct is not None else 20.0
        if state.request:
            if state.request.override_soil_moisture_pct is not None:
                moisture = float(state.request.override_soil_moisture_pct)
            if state.request.override_field_capacity_pct is not None:
                fc = float(state.request.override_field_capacity_pct)
            if state.request.override_wilting_point_pct is not None:
                wp = float(state.request.override_wilting_point_pct)

        status = compute_soil_water_status(
            moisture_pct=moisture,
            field_capacity_pct=fc,
            wilting_point_pct=wp,
            root_depth_m=root_depth_m,
            depletion_fraction_p=p_fraction,
        )

        # Step 5: Build SoilContext
        soil_type_name = (
            state.request.override_soil_type
            if (state.request and state.request.override_soil_type)
            else self._classify_soil_type(profile)
        )
        evidence = [
            f"Soil Volumetric Moisture = {status.volumetric_moisture_pct:.1f}%",
            f"Field Capacity = {status.field_capacity_pct:.1f}%, Wilting Point = {status.wilting_point_pct:.1f}%",
            f"Available Water Content = {status.available_water_pct:.1f}% of TAW",
            f"Total Available Water (TAW) = {status.taw_mm:.1f} mm across {status.root_depth_m:.2f} m root zone",
            f"Readily Available Water (RAW) = {status.raw_mm:.1f} mm (depletion fraction p={status.depletion_fraction_p:.2f})",
            f"Root Zone Depletion (Dr) = {status.depletion_mm:.1f} mm",
            f"FAO-56 Water Stress Coefficient Ks = {status.ks:.2f} (Soil Stress Index = {status.soil_stress_index:.2f})",
            f"Soil Condition: {status.condition_label}",
        ]

        if crop_name:
            evidence.append(f"Crop: {crop_name} (effective root depth {root_depth_m:.2f} m)")

        if status.is_over_wet:
            evidence.append("WARNING: Moisture exceeds field capacity; potential waterlogging / anaerobic stress.")
        elif status.is_over_dry:
            evidence.append("CRITICAL: Moisture at or below permanent wilting point; severe plant dehydration risk.")

        confidence = 0.90 if not is_fallback else 0.60

        state.soil = SoilContext(
            zone_id=zone.id,
            soil_type=soil_type_name,
            soil_moisture_pct=status.volumetric_moisture_pct,
            field_capacity_pct=status.field_capacity_pct,
            wilting_point_pct=status.wilting_point_pct,
            available_water_pct=status.available_water_pct,
            water_holding_capacity_mm=status.taw_mm,
            soil_stress_index=status.soil_stress_index,
            is_over_wet=status.is_over_wet,
            is_over_dry=status.is_over_dry,
            soil_condition=status.condition_label,
            confidence=confidence,
            evidence=evidence,
            data_source=profile.data_source or "simulated",
        )

        self._log_info(
            "SoilAgent: completed analysis for Zone %d — Moisture=%.1f%%, AW=%.1f%%, StressIndex=%.2f, Condition=%s",
            zone.id,
            status.volumetric_moisture_pct,
            status.available_water_pct,
            status.soil_stress_index,
            status.condition_label,
        )
        return state

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #

    def _resolve_target_zone(self, state: AgentState) -> Zone | None:
        """Identify which zone to evaluate based on request context."""
        req = state.request
        if not req:
            return None

        # 1. Direct zone_ids
        if req.zone_ids:
            return self._zone_repo.get_by_id(req.zone_ids[0])

        # 2. Field ID
        if req.field_id:
            zones = self._zone_repo.get_active_zones(req.field_id)
            return zones[0] if zones else None

        # 3. Farm ID
        if req.farm_id:
            fields = self._field_repo.get_by_farm(req.farm_id)
            for field in fields:
                zones = self._zone_repo.get_active_zones(field.id)
                if zones:
                    return zones[0]

        return None

    def _resolve_crop_parameters(self, zone: Zone) -> tuple[float, float, str | None]:
        """
        Derive root depth Zr (m) and depletion fraction p from zone's crop.
        Defaults to 0.3m and 0.5 if crop info is not available.
        """
        root_depth_m = 0.3
        p_fraction = 0.5
        crop_name = zone.crop_name

        if crop_name:
            crop = self._crop_repo.get_by_name(crop_name)
            if crop:
                if crop.depletion_fraction_p:
                    p_fraction = crop.depletion_fraction_p
                # Check for active growth stage for root depth
                stage = self._stage_repo.get_current_for_zone(zone.id)
                if stage and stage.current_root_depth_m:
                    root_depth_m = stage.current_root_depth_m
                elif crop.root_depth_initial_m:
                    root_depth_m = crop.root_depth_initial_m

        return root_depth_m, p_fraction, crop_name

    @staticmethod
    def _classify_soil_type(profile: SoilProfile) -> str:
        """Classify soil texture name from sand/silt/clay or notes."""
        if profile.notes and "Sandy Loam" in profile.notes:
            return "Sandy Loam"
        if profile.sand_pct is not None and profile.clay_pct is not None:
            sand = profile.sand_pct
            clay = profile.clay_pct
            if sand >= 70:
                return "Sandy Loam" if clay >= 10 else "Sand"
            if clay >= 40:
                return "Clay"
            if 20 <= clay < 40:
                return "Clay Loam"
            return "Loam"
        return "Sandy Loam"

    @staticmethod
    def _generate_simulated_profile(zone: Zone) -> SoilProfile:
        """Generate simulated profile matching FAO-56 Sandy Loam reference."""
        defaults = SOIL_TEXTURE_DEFAULTS["Sandy Loam"]
        return SoilProfile(
            zone_id=zone.id,
            data_source="simulated",
            volumetric_moisture_pct=18.0,
            field_capacity_pct=defaults["fc"],
            wilting_point_pct=defaults["wp"],
            bulk_density_g_cm3=1.45,
            ph=6.8,
            organic_matter_pct=1.5,
            sand_pct=65.0,
            silt_pct=20.0,
            clay_pct=15.0,
            depth_cm=30.0,
            notes="Simulated Sandy Loam fallback profile.",
        )

    @staticmethod
    def _empty_soil(reason: str, zone_id: int | None = None) -> SoilContext:
        """Create empty SoilContext on error/missing data."""
        return SoilContext(
            zone_id=zone_id,
            soil_type="Unknown",
            soil_moisture_pct=None,
            field_capacity_pct=None,
            wilting_point_pct=None,
            available_water_pct=None,
            water_holding_capacity_mm=None,
            soil_stress_index=0.0,
            is_over_wet=False,
            is_over_dry=False,
            soil_condition=f"Unavailable: {reason}",
            confidence=0.0,
            data_source="none",
            evidence=[f"Analysis skipped: {reason}"],
        )

