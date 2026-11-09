"""
Zone-Level & Multi-Zone Irrigation Agent.

Responsibilities
----------------
1. Discover all active zones across the farm or field footprint.
2. Evaluate heterogeneous soil profiles and distinct planted crops per zone.
3. Compute independent root-zone depletion, TAW, RAW, and stress indices for each zone.
4. Calculate zone-specific Net Irrigation Requirements (NIR) and physical emitter bounds.
5. Generate individual ``ZoneIrrigationPlan`` objects.
6. Populate ``state.zone_plans`` in the shared AgentState.

ARCHITECTURAL CONSTRAINT (from project spec):
    This agent writes ONLY to the ``zone_plans`` section of AgentState.
    ALL zone calculations and priority allocations derive from validated soil physics,
    crop coefficients, and hydraulic bounds — NEVER from LLM hallucinations.
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
from app.schemas.agent_state import AgentState, IrrigationPriority, ZoneIrrigationPlan
from app.service.crop_phenology import determine_growth_stage_and_kc
from app.service.irrigation_rules import DecisionOutcome, evaluate_irrigation_decision
from app.service.soil_physics import compute_soil_water_status

logger = logging.getLogger(__name__)


class ZoneIrrigationAgent(BaseAgent):
    """
    Zone-Level Irrigation Agent.

    Generates customized, zone-specific irrigation schedules tailored to
    varying soil textures, micro-climates, and crop varieties.

    Writes to
    ---------
    * ``state.zone_plans`` — list[ZoneIrrigationPlan]

    Configuration keys
    ------------------
    ``db`` : SQLAlchemy Session (required)
    """

    name = AgentType.ZONE_IRRIGATION.value
    timeout_seconds = 45.0

    def __init__(self, db: Session, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._db = db
        self._zone_repo = ZoneRepository(db)
        self._soil_repo = SoilProfileRepository(db)
        self._crop_repo = CropRepository(db)
        self._stage_repo = CropGrowthStageRepository(db)
        self._field_repo = FieldRepository(db)
        self._farm_repo = FarmRepository(db)

    # ------------------------------------------------------------------ #
    # Core agent logic
    # ------------------------------------------------------------------ #

    def _run(self, state: AgentState) -> AgentState:
        """
        Execute multi-zone precision irrigation scheduling.

        Steps:
        1. Resolve all candidate active zones.
        2. Ingest zone-specific soil profiles and crop parameters.
        3. Evaluate soil water balance and crop evapotranspiration per zone.
        4. Execute decision logic per zone.
        5. Build and populate state.zone_plans.
        """
        active_zones = self._discover_active_zones(state)
        if not active_zones:
            self._add_warning(state, "No active zones found for multi-zone planning.")
            state.zone_plans = []
            return state

        self._log_info("ZoneIrrigationAgent: evaluating %d active zones", len(active_zones))

        # Weather factors common across field
        w = state.weather
        weather_suitable = w.irrigation_suitable if w else None
        precip_mm = w.rainfall_mm or 0.0 if w else 0.0
        forecast_rain_mm = w.forecast_rainfall_7d_mm or 0.0 if w else 0.0
        wind_ms = w.wind_speed_ms or 0.0 if w else 0.0
        temp_c = w.temperature_c if (w and w.temperature_c is not None) else 25.0

        # Baseline reference ET0
        et0_mm = 4.5
        if state.et0 and state.et0.et0_reference_mm is not None:
            et0_mm = state.et0.et0_reference_mm
        elif state.et0 and state.et0.et0_predicted_mm is not None:
            et0_mm = state.et0.et0_predicted_mm

        moisture_override = (
            state.request.override_soil_moisture_pct
            if state.request and state.request.override_soil_moisture_pct is not None
            else None
        )

        zone_plans: list[ZoneIrrigationPlan] = []

        for zone in active_zones:
            plan = self._evaluate_zone_plan(
                zone=zone,
                weather_suitable=weather_suitable,
                precip_mm=precip_mm,
                forecast_rain_mm=forecast_rain_mm,
                wind_ms=wind_ms,
                temp_c=temp_c,
                et0_mm=et0_mm,
                moisture_override=moisture_override,
            )
            zone_plans.append(plan)

        state.zone_plans = zone_plans

        self._log_info(
            "ZoneIrrigationAgent: generated %d zone plans — %d zones requiring irrigation",
            len(zone_plans),
            sum(1 for p in zone_plans if p.irrigation_required),
        )
        return state

    # ------------------------------------------------------------------ #
    # Per-zone evaluation
    # ------------------------------------------------------------------ #

    def _evaluate_zone_plan(
        self,
        zone: Zone,
        weather_suitable: bool | None,
        precip_mm: float,
        forecast_rain_mm: float,
        wind_ms: float,
        temp_c: float,
        et0_mm: float,
        moisture_override: float | None = None,
    ) -> ZoneIrrigationPlan:
        """Calculate complete irrigation plan for a single zone."""
        # 1. Fetch latest SoilProfile or default Sandy Loam
        profile = self._soil_repo.get_latest_for_zone(zone.id)
        fc = profile.field_capacity_pct if (profile and profile.field_capacity_pct) else 25.0
        wp = profile.wilting_point_pct if (profile and profile.wilting_point_pct) else 10.0
        moisture = profile.volumetric_moisture_pct if (profile and profile.volumetric_moisture_pct is not None) else 18.0
        if moisture_override is not None:
            moisture = float(moisture_override)

        # 2. Derive Crop Constants & Kc
        crop_name = zone.crop_name or "Wheat"
        crop = self._crop_repo.get_by_name(crop_name)
        root_depth_m = 0.3
        p_depletion = 0.5
        kc_val = 1.0

        if crop:
            p_depletion = crop.depletion_fraction_p or 0.5
            # Check existing growth stage
            stage = self._stage_repo.get_current_for_zone(zone.id)
            if stage:
                kc_val = stage.current_kc
                root_depth_m = stage.current_root_depth_m
            else:
                growth_status = determine_growth_stage_and_kc(
                    days_after_planting=45,
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
                )
                kc_val = growth_status.current_kc
                root_depth_m = growth_status.current_root_depth_m

        # 3. Compute Soil Water Balance
        soil_status = compute_soil_water_status(
            moisture_pct=moisture,
            field_capacity_pct=fc,
            wilting_point_pct=wp,
            root_depth_m=root_depth_m,
            depletion_fraction_p=p_depletion,
        )

        etc_zone_mm = kc_val * et0_mm
        min_depth = zone.min_irrigation_mm or 5.0
        max_depth = zone.max_irrigation_mm or 35.0

        # 4. Evaluate Decision Rules for this specific Zone
        outcome: DecisionOutcome = evaluate_irrigation_decision(
            weather_suitable=weather_suitable,
            precipitation_mm=precip_mm,
            rainfall_forecast_mm=forecast_rain_mm,
            wind_speed_ms=wind_ms,
            temperature_c=temp_c,
            is_over_wet=soil_status.is_over_wet,
            is_over_dry=soil_status.is_over_dry,
            soil_stress_index=soil_status.soil_stress_index,
            available_water_pct=soil_status.available_water_pct,
            water_holding_capacity_mm=soil_status.taw_mm,
            etc_mm=etc_zone_mm,
            crop_growth_stage="mid",
            min_irrigation_mm=min_depth,
            max_irrigation_mm=max_depth,
        )

        evidence = [
            f"Zone: {zone.name} (Area: {zone.area_ha:.2f} ha, Crop: {crop_name})",
            f"Soil Moisture: {soil_status.volumetric_moisture_pct:.1f}% (AW%: {soil_status.available_water_pct:.1f}%, TAW: {soil_status.taw_mm:.1f} mm)",
            f"Crop Demand: {etc_zone_mm:.2f} mm/day (Kc={kc_val:.3f}, ET0={et0_mm:.2f} mm/day)",
            f"Stress Index: {soil_status.soil_stress_index:.2f} ({soil_status.condition_label})",
            f"Decision: {outcome.decision.value} (Priority: {outcome.priority.value})",
        ]

        if outcome.postponement_reason:
            evidence.append(f"Postponement: {outcome.postponement_reason}")
        elif outcome.recommended_volume_mm > 0:
            evidence.append(f"Recommended Volume: {outcome.recommended_volume_mm:.1f} mm via {zone.irrigation_method or 'drip'}")

        return ZoneIrrigationPlan(
            zone_id=zone.id,
            zone_name=zone.name,
            irrigation_required=(outcome.decision.value == "REQUIRED"),
            recommended_volume_mm=outcome.recommended_volume_mm,
            priority=outcome.priority,
            stress_index=soil_status.soil_stress_index,
            confidence=outcome.confidence,
            evidence=evidence,
        )

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #

    def _discover_active_zones(self, state: AgentState) -> list[Zone]:
        """Resolve all zones that need evaluation."""
        req = state.request

        # 1. Explicit zone_ids requested
        if req and req.zone_ids:
            zones = [self._zone_repo.get_by_id(zid) for zid in req.zone_ids]
            return [z for z in zones if z is not None and z.is_active]

        # 2. Field ID
        if req and req.field_id:
            return list(self._zone_repo.get_active_zones(req.field_id))

        # 3. Farm ID
        if req and req.farm_id:
            fields = self._field_repo.get_by_farm(req.farm_id)
            zones = []
            for f in fields:
                zones.extend(self._zone_repo.get_active_zones(f.id))
            return zones

        # 4. Fallback: all active zones in demo farm
        demo_farm = self._farm_repo.get_by_name("Autonomous Demo Farm")
        if demo_farm:
            fields = self._field_repo.get_by_farm(demo_farm.id)
            zones = []
            for f in fields:
                zones.extend(self._zone_repo.get_active_zones(f.id))
            return zones

        return []

