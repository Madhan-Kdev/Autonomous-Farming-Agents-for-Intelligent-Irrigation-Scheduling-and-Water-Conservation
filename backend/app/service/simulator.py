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
class SimulationStepResult:
    """Telemetry outputs from a simulation advance step."""

    target_date: date
    weather_record_id: int
    soil_profiles_updated: list[int]
    simulated_et0_mm: float
    simulated_rain_mm: float
    zone_moisture_levels: dict[int, float]


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
