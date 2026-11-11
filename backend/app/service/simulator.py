r"""
Virtual IoT and Autonomous Farming Telemetry Simulation Engine.

Generates realistic physical sensor telemetry and dynamic agricultural cycles
for soil moisture, agro-meteorological conditions, and crop progression.

Capabilities:
1. Dynamic Soil Moisture Balance Simulation:
   - Evapotranspiration depletion ($D_r = D_{r, prev} + ET_c - P_{eff} - I_{net}$).
   - Drainage when moisture exceeds Field Capacity.
   - Sensor noise and measurement jitter (+/- 0.5%).
2. Weather Telemetry Simulation:
   - Diurnal solar radiation and temperature cycles.
   - Realistic rain events and wind fluctuations.
3. Multi-Day Autonomous Environmental Stepping:
   - Advance farm days forward.
   - Simulate historical seasons and drydown spells.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import math
import random
from typing import Sequence

from sqlalchemy.orm import Session

from app.models.crop import CropGrowthStage
from app.models.weather import WeatherRecord
from app.models.zone import SoilProfile, Zone
from app.service.soil_physics import compute_soil_water_status
from app.repositories.repositories import (
    CropGrowthStageRepository,
    CropRepository,
    FarmRepository,
    FieldRepository,
    IrrigationRecordRepository,
    SoilProfileRepository,
    WeatherRecordRepository,
    ZoneRepository,
)


@dataclass
class ManualIrrigationResult:
    """Telemetry outputs from a direct manual irrigation application."""

    zone_id: int
    zone_name: str
    farm_id: int
    volume_applied_mm: float
    volume_applied_liters: float
    duration_minutes: float
    flow_rate_l_h: float
    irrigation_method: str
    soil_moisture_before_pct: float
    soil_moisture_after_pct: float
    field_capacity_pct: float
    wilting_point_pct: float
    deep_percolation_mm: float
    stress_index_before: float
    stress_index_after: float
    irrigation_record_id: int
    soil_profile_id: int


@dataclass
class SimulationStepResult:
    """Telemetry outputs from a simulation advance step."""

    target_date: date
    weather_record_id: int
    soil_profiles_updated: list[int]
    simulated_et0_mm: float
    simulated_rain_mm: float
    zone_moisture_levels: dict[int, float]


@dataclass
class BatchSimulationResult:
    """Telemetry outputs from a multi-day batch simulation."""

    farm_id: int
    days_simulated: int
    start_date: date
    end_date: date
    daily_results: list[SimulationStepResult]
    total_rain_mm: float
    total_et0_mm: float
    zone_final_moistures: dict[int, float]
    zone_stress_days: dict[int, int]


class VirtualFarmSimulator:
    """
    Simulates agricultural physics and virtual IoT telemetry across farm zones.
    """

    def __init__(self, db: Session, seed: int = 42) -> None:
        self.db = db
        self.rng = random.Random(seed)
        self.farm_repo = FarmRepository(db)
        self.field_repo = FieldRepository(db)
        self.zone_repo = ZoneRepository(db)
        self.soil_repo = SoilProfileRepository(db)
        self.weather_repo = WeatherRecordRepository(db)
        self.crop_repo = CropRepository(db)
        self.stage_repo = CropGrowthStageRepository(db)
        self.irrig_repo = IrrigationRecordRepository(db)

    def advance_day(
        self,
        farm_id: int,
        target_date: date | None = None,
        irrigation_events: dict[int, float] | None = None,
        force_rain_mm: float | None = None,
    ) -> SimulationStepResult:
        """
        Advance the virtual farm by one 24-hour cycle.

        Parameters
        ----------
        farm_id : int
            Target farm ID.
        target_date : date, optional
            The date to simulate. Defaults to tomorrow after latest weather record or today.
        irrigation_events : dict[int, float], optional
            Mapping of zone_id -> applied irrigation depth in mm.
        force_rain_mm : float, optional
            Force a specific rainfall depth for testing.

        Returns
        -------
        SimulationStepResult
        """
        farm = self.farm_repo.get_by_id(farm_id)
        if not farm:
            raise ValueError(f"Farm {farm_id} not found.")

        # Determine target date
        if target_date is None:
            recent_w = self.weather_repo.get_recent(farm_id, days=1)
            if recent_w:
                target_date = recent_w[0].observation_date + timedelta(days=1)
            else:
                target_date = date.today()

        # 1. Simulate Weather Telemetry
        temp_mean = round(self.rng.uniform(22.0, 32.0), 1)
        temp_max = round(temp_mean + self.rng.uniform(4.0, 8.0), 1)
        temp_min = round(temp_mean - self.rng.uniform(4.0, 7.0), 1)
        humidity_mean = round(self.rng.uniform(40.0, 75.0), 1)
        wind_speed = round(self.rng.uniform(1.2, 5.5), 1)
        solar_rad = round(self.rng.uniform(16.0, 24.0), 1)

        if force_rain_mm is not None:
            rain_mm = round(force_rain_mm, 1)
        else:
            # 15% chance of rain
            rain_mm = round(self.rng.uniform(3.0, 22.0), 1) if self.rng.random() < 0.15 else 0.0

        # Compute FAO-56 Penman-Monteith ET0 estimate
        # Simplified radiation-temperature approximation for simulation dynamics
        et0_approx = max(1.5, round(0.0023 * (temp_mean + 17.8) * math.sqrt(temp_max - temp_min) * (solar_rad * 0.408), 2))

        # Check existing weather record or create
        weather_rec = self.weather_repo.get_for_date(farm_id, target_date)
        if not weather_rec:
            weather_rec = self.weather_repo.create(
                farm_id=farm_id,
                observation_date=target_date,
                source="simulated",
                temperature_max_c=temp_max,
                temperature_min_c=temp_min,
                temperature_mean_c=temp_mean,
                humidity_max_pct=min(100.0, humidity_mean + 15.0),
                humidity_min_pct=max(15.0, humidity_mean - 15.0),
                humidity_mean_pct=humidity_mean,
                wind_speed_m_s=wind_speed,
                solar_radiation_mj_m2=solar_rad,
                precipitation_mm=rain_mm,
            )

        # 2. Simulate Zone-Level Soil Moisture Dynamics
        fields = self.field_repo.get_by_farm(farm_id)
        updated_profiles = []
        zone_moistures = {}

        irrig_map = irrigation_events or {}

        for field in fields:
            zones = self.zone_repo.get_active_zones(field.id)
            for zone in zones:
                latest_soil = self.soil_repo.get_latest_for_zone(zone.id)
                fc = latest_soil.field_capacity_pct if (latest_soil and latest_soil.field_capacity_pct) else 30.0
                wp = latest_soil.wilting_point_pct if (latest_soil and latest_soil.wilting_point_pct) else 12.0
                curr_theta = latest_soil.volumetric_moisture_pct if (latest_soil and latest_soil.volumetric_moisture_pct) else 22.0

                # Crop demand
                kc = 1.0
                if zone.crop_name:
                    crop = self.crop_repo.get_by_name(zone.crop_name)
                    if crop:
                        kc = crop.kc_mid

                etc = et0_approx * kc
                irrig_mm = irrig_map.get(zone.id, 0.0)

                # Depth conversion: 300 mm root zone depth
                # delta_theta (%) = (Rainfall + Irrigation - ETc) / 300 mm * 100
                delta_pct = ((rain_mm * 0.8) + irrig_mm - etc) / 300.0 * 100.0
                noise = self.rng.uniform(-0.3, 0.3)

                new_theta = max(wp * 0.7, min(fc * 1.10, curr_theta + delta_pct + noise))
                new_theta = round(new_theta, 1)

                new_profile = self.soil_repo.create(
                    zone_id=zone.id,
                    data_source="simulated",
                    volumetric_moisture_pct=new_theta,
                    field_capacity_pct=fc,
                    wilting_point_pct=wp,
                    bulk_density_g_cm3=latest_soil.bulk_density_g_cm3 if latest_soil else 1.45,
                    ph=latest_soil.ph if latest_soil else 6.8,
                    organic_matter_pct=latest_soil.organic_matter_pct if latest_soil else 1.2,
                    sand_pct=latest_soil.sand_pct if latest_soil else 65.0,
                    silt_pct=latest_soil.silt_pct if latest_soil else 20.0,
                    clay_pct=latest_soil.clay_pct if latest_soil else 15.0,
                    depth_cm=30.0,
                    temperature_c=round(temp_mean - 2.0, 1),
                    notes=f"Simulated daily telemetry update for {target_date.isoformat()}",
                )
                updated_profiles.append(new_profile.id)
                zone_moistures[zone.id] = new_theta

        return SimulationStepResult(
            target_date=target_date,
            weather_record_id=weather_rec.id,
            soil_profiles_updated=updated_profiles,
            simulated_et0_mm=et0_approx,
            simulated_rain_mm=rain_mm,
            zone_moisture_levels=zone_moistures,
        )

    def apply_zone_manual_irrigation(
        self,
        zone_id: int,
        volume_mm: float | None = None,
        volume_liters: float | None = None,
        irrigation_method: str | None = None,
        flow_rate_l_h: float | None = None,
    ) -> ManualIrrigationResult:
        """
        Execute an immediate manual irrigation event on a specific zone in the virtual farm.

        Calculates volume conversion, application efficiency, soil moisture refill,
        deep percolation losses, flow duration, and soil stress transitions,
        persisting both a new SoilProfile telemetry record and an applied IrrigationRecord.
        """
        zone = self.zone_repo.get_by_id(zone_id)
        if not zone:
            raise ValueError(f"Zone with ID {zone_id} does not exist.")

        field = self.field_repo.get_by_id(zone.field_id) if zone.field_id else None
        farm_id = field.farm_id if field else 1
        area_ha = float(zone.area_ha) if zone.area_ha else 1.0

        # 1. Volume normalization (1 mm over 1 ha = 10,000 L)
        if volume_mm is not None and volume_mm > 0:
            vol_mm = float(volume_mm)
            vol_liters = vol_mm * area_ha * 10000.0
        elif volume_liters is not None and volume_liters > 0:
            vol_liters = float(volume_liters)
            vol_mm = vol_liters / (area_ha * 10000.0)
        else:
            raise ValueError("Either volume_mm (>0) or volume_liters (>0) must be specified.")

        # 2. Irrigation method efficiency (eta)
        method = (irrigation_method or zone.irrigation_method or "drip").lower()
        efficiencies = {
            "drip": 0.90,
            "sprinkler": 0.80,
            "flood": 0.65,
            "surface": 0.65,
        }
        eta = efficiencies.get(method, 0.85)
        net_inflow_mm = vol_mm * eta

        # 3. Flow rate and pumping duration
        if flow_rate_l_h is not None and flow_rate_l_h > 0:
            q = float(flow_rate_l_h)
        else:
            q = 25000.0 * area_ha  # Default 25,000 L/h per hectare
        duration_minutes = (vol_liters / q) * 60.0 if q > 0 else 0.0

        # 4. Current soil status
        latest_soil = self.soil_repo.get_latest_for_zone(zone.id)
        fc = latest_soil.field_capacity_pct if (latest_soil and latest_soil.field_capacity_pct) else 30.0
        wp = latest_soil.wilting_point_pct if (latest_soil and latest_soil.wilting_point_pct) else 12.0
        curr_theta = latest_soil.volumetric_moisture_pct if (latest_soil and latest_soil.volumetric_moisture_pct) else 22.0
        root_depth_m = (latest_soil.depth_cm / 100.0) if (latest_soil and latest_soil.depth_cm) else 0.40

        # 5. Moisture replenishment & percolation physics
        # delta_theta (%) = net_inflow_mm / (10.0 * root_depth_m)
        delta_theta = net_inflow_mm / (10.0 * root_depth_m)
        theta_theo = curr_theta + delta_theta

        if theta_theo > fc:
            theta_after = fc
            excess_pct = theta_theo - fc
            deep_percolation_mm = excess_pct * 10.0 * root_depth_m
        else:
            theta_after = theta_theo
            deep_percolation_mm = 0.0

        theta_after = round(theta_after, 2)
        deep_percolation_mm = round(deep_percolation_mm, 2)

        # 6. Soil water stress before and after
        status_before = compute_soil_water_status(
            moisture_pct=curr_theta,
            field_capacity_pct=fc,
            wilting_point_pct=wp,
            root_depth_m=root_depth_m,
        )
        status_after = compute_soil_water_status(
            moisture_pct=theta_after,
            field_capacity_pct=fc,
            wilting_point_pct=wp,
            root_depth_m=root_depth_m,
        )

        # 7. Persist updated SoilProfile
        new_profile = self.soil_repo.create(
            zone_id=zone.id,
            data_source="simulated",
            volumetric_moisture_pct=theta_after,
            field_capacity_pct=fc,
            wilting_point_pct=wp,
            bulk_density_g_cm3=latest_soil.bulk_density_g_cm3 if latest_soil else 1.45,
            ph=latest_soil.ph if latest_soil else 6.8,
            organic_matter_pct=latest_soil.organic_matter_pct if latest_soil else 1.2,
            sand_pct=latest_soil.sand_pct if latest_soil else 65.0,
            silt_pct=latest_soil.silt_pct if latest_soil else 20.0,
            clay_pct=latest_soil.clay_pct if latest_soil else 15.0,
            depth_cm=root_depth_m * 100.0,
            temperature_c=latest_soil.temperature_c if latest_soil else 22.0,
            notes=f"Manual irrigation applied: {round(vol_mm, 2)} mm ({round(vol_liters, 1)} L) via {method}",
        )

        # 8. Persist applied IrrigationRecord
        now = datetime.now(timezone.utc)
        irrig_rec = self.irrig_repo.create(
            zone_id=zone.id,
            farm_id=farm_id,
            scheduled_at=now,
            decision="MANUAL_COMMAND",
            recommended_volume_mm=round(vol_mm, 2),
            recommended_duration_min=round(duration_minutes, 1),
            actual_volume_mm=round(vol_mm, 2),
            actual_duration_min=round(duration_minutes, 1),
            was_applied=True,
            soil_moisture_before_pct=round(curr_theta, 2),
            soil_moisture_after_pct=theta_after,
            et0_on_day_mm=None,
            etc_on_day_mm=None,
            precipitation_on_day_mm=0.0,
            decision_confidence=1.0,
            irrigation_method=method,
            reasoning_summary=f"Manual operator irrigation: {round(vol_mm, 2)} mm ({round(vol_liters, 1)} L), duration {round(duration_minutes, 1)} min.",
            notes="Direct manual digital twin command execution.",
        )

        self.db.commit()
        self.db.refresh(new_profile)
        self.db.refresh(irrig_rec)

        return ManualIrrigationResult(
            zone_id=zone.id,
            zone_name=zone.name,
            farm_id=farm_id,
            volume_applied_mm=round(vol_mm, 2),
            volume_applied_liters=round(vol_liters, 1),
            duration_minutes=round(duration_minutes, 1),
            flow_rate_l_h=round(q, 1),
            irrigation_method=method,
            soil_moisture_before_pct=round(curr_theta, 2),
            soil_moisture_after_pct=theta_after,
            field_capacity_pct=round(fc, 2),
            wilting_point_pct=round(wp, 2),
            deep_percolation_mm=deep_percolation_mm,
            stress_index_before=round(status_before.soil_stress_index, 4),
            stress_index_after=round(status_after.soil_stress_index, 4),
            irrigation_record_id=irrig_rec.id,
            soil_profile_id=new_profile.id,
        )

    def batch_advance(
        self,
        farm_id: int,
        days: int = 7,
        force_rain_daily_mm: float | None = None,
        zone_irrigation_daily_mm: dict[int, float] | None = None,
        auto_irrigate_threshold_pct: float | None = None,
    ) -> BatchSimulationResult:
        """
        Simulate multiple consecutive days across all zones in a virtual farm.

        Parameters
        ----------
        farm_id : int
            Target farm ID.
        days : int
            Number of consecutive 24-hour cycles to simulate (1 to 60).
        force_rain_daily_mm : float | None
            Fixed rainfall to apply every day (e.g. 0.0 for drought / drydown scenario).
        zone_irrigation_daily_mm : dict[int, float] | None
            Scheduled daily irrigation per zone in mm.
        auto_irrigate_threshold_pct : float | None
            If specified, any zone whose moisture falls below this threshold
            automatically receives refill irrigation.

        Returns
        -------
        BatchSimulationResult
        """
        if days < 1 or days > 60:
            raise ValueError("days must be between 1 and 60.")

        farm = self.farm_repo.get_by_id(farm_id)
        if not farm:
            raise ValueError(f"Farm {farm_id} not found.")

        daily_results: list[SimulationStepResult] = []
        total_rain = 0.0
        total_et0 = 0.0
        stress_days_counter: dict[int, int] = {}

        fields = self.field_repo.get_by_farm(farm_id)
        all_zones = []
        for f in fields:
            all_zones.extend(self.zone_repo.get_active_zones(f.id))

        for z in all_zones:
            stress_days_counter[z.id] = 0

        for _ in range(days):
            day_irrigation: dict[int, float] = {}
            if zone_irrigation_daily_mm:
                day_irrigation.update(zone_irrigation_daily_mm)

            if auto_irrigate_threshold_pct is not None:
                for z in all_zones:
                    latest_soil = self.soil_repo.get_latest_for_zone(z.id)
                    curr = latest_soil.volumetric_moisture_pct if latest_soil else 22.0
                    fc = latest_soil.field_capacity_pct if latest_soil else 30.0
                    if curr <= auto_irrigate_threshold_pct:
                        refill_mm = max(10.0, round(((fc - curr) / 100.0) * 300.0 / 0.9, 1))
                        day_irrigation[z.id] = max(day_irrigation.get(z.id, 0.0), refill_mm)

            step_res = self.advance_day(
                farm_id=farm_id,
                target_date=None,
                irrigation_events=day_irrigation,
                force_rain_mm=force_rain_daily_mm,
            )
            daily_results.append(step_res)
            total_rain += step_res.simulated_rain_mm
            total_et0 += step_res.simulated_et0_mm

            for z in all_zones:
                m = step_res.zone_moisture_levels.get(z.id)
                latest_soil = self.soil_repo.get_latest_for_zone(z.id)
                wp = latest_soil.wilting_point_pct if latest_soil else 12.0
                if m is not None and m <= (wp + 3.0):
                    stress_days_counter[z.id] += 1

        final_moistures = daily_results[-1].zone_moisture_levels if daily_results else {}

        return BatchSimulationResult(
            farm_id=farm_id,
            days_simulated=days,
            start_date=daily_results[0].target_date,
            end_date=daily_results[-1].target_date,
            daily_results=daily_results,
            total_rain_mm=round(total_rain, 1),
            total_et0_mm=round(total_et0, 1),
            zone_final_moistures=final_moistures,
            zone_stress_days=stress_days_counter,
        )
