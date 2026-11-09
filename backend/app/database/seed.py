"""
Database seed script for Phase 3.

Seeds the database with:
1. FAO-56 validated crop data (Kc coefficients from Allen et al., 1998).
2. A demo farm with 1 field and 3 zones for development/testing.
3. A demo soil profile for each zone (simulated, labelled as such).

This script is idempotent — running it multiple times does NOT create
duplicate records.  It checks for existence before inserting.

Usage (from backend/ directory with venv active):
    python -m app.database.seed
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow running as a module from the backend/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:FarmAgent2024!@localhost:5432/autonomous_farming",
)
os.environ.setdefault("DEBUG", "false")

from app.database.engine import SessionLocal
from app.models import (  # noqa: F401 — ensures models are registered
    Crop, Farm, Field, SoilProfile, Zone,
)
from app.repositories.repositories import (
    CropRepository,
    FarmRepository,
    FieldRepository,
    SoilProfileRepository,
    ZoneRepository,
)

logger = logging.getLogger(__name__)


# ================================================================== #
# FAO-56 Crop Data (Allen et al., 1998, Table 12 + Table 22)
# All Kc values are from peer-reviewed literature — NOT LLM generated.
# ================================================================== #

FAO56_CROPS = [
    {
        "name": "Wheat",
        "scientific_name": "Triticum aestivum",
        "crop_type": "cereal",
        "kc_initial": 0.3,
        "kc_mid": 1.15,
        "kc_end": 0.25,
        "root_depth_initial_m": 0.15,
        "root_depth_max_m": 1.50,
        "depletion_fraction_p": 0.55,
        "days_initial": 15,
        "days_development": 30,
        "days_mid": 65,
        "days_late": 40,
        "total_growing_days": 150,
        "reference": "FAO-56 Table 12, Allen et al. (1998)",
    },
    {
        "name": "Maize",
        "scientific_name": "Zea mays",
        "crop_type": "cereal",
        "kc_initial": 0.3,
        "kc_mid": 1.20,
        "kc_end": 0.35,
        "root_depth_initial_m": 0.15,
        "root_depth_max_m": 1.70,
        "depletion_fraction_p": 0.55,
        "days_initial": 20,
        "days_development": 35,
        "days_mid": 40,
        "days_late": 30,
        "total_growing_days": 125,
        "reference": "FAO-56 Table 12, Allen et al. (1998)",
    },
    {
        "name": "Rice",
        "scientific_name": "Oryza sativa",
        "crop_type": "cereal",
        "kc_initial": 1.05,
        "kc_mid": 1.20,
        "kc_end": 0.90,
        "root_depth_initial_m": 0.10,
        "root_depth_max_m": 0.50,
        "depletion_fraction_p": 0.20,
        "days_initial": 30,
        "days_development": 30,
        "days_mid": 80,
        "days_late": 40,
        "total_growing_days": 180,
        "reference": "FAO-56 Table 12, Allen et al. (1998)",
    },
    {
        "name": "Tomato",
        "scientific_name": "Solanum lycopersicum",
        "crop_type": "vegetable",
        "kc_initial": 0.6,
        "kc_mid": 1.15,
        "kc_end": 0.70,
        "root_depth_initial_m": 0.15,
        "root_depth_max_m": 0.70,
        "depletion_fraction_p": 0.40,
        "days_initial": 30,
        "days_development": 40,
        "days_mid": 40,
        "days_late": 25,
        "total_growing_days": 135,
        "reference": "FAO-56 Table 12, Allen et al. (1998)",
    },
    {
        "name": "Cotton",
        "scientific_name": "Gossypium hirsutum",
        "crop_type": "fiber",
        "kc_initial": 0.35,
        "kc_mid": 1.15,
        "kc_end": 0.50,
        "root_depth_initial_m": 0.15,
        "root_depth_max_m": 1.70,
        "depletion_fraction_p": 0.65,
        "days_initial": 30,
        "days_development": 50,
        "days_mid": 60,
        "days_late": 55,
        "total_growing_days": 195,
        "reference": "FAO-56 Table 12, Allen et al. (1998)",
    },
    {
        "name": "Sugarcane",
        "scientific_name": "Saccharum officinarum",
        "crop_type": "sugar",
        "kc_initial": 0.40,
        "kc_mid": 1.25,
        "kc_end": 0.75,
        "root_depth_initial_m": 0.20,
        "root_depth_max_m": 1.20,
        "depletion_fraction_p": 0.65,
        "days_initial": 35,
        "days_development": 60,
        "days_mid": 190,
        "days_late": 120,
        "total_growing_days": 405,
        "reference": "FAO-56 Table 12, Allen et al. (1998)",
    },
    {
        "name": "Soybean",
        "scientific_name": "Glycine max",
        "crop_type": "legume",
        "kc_initial": 0.40,
        "kc_mid": 1.15,
        "kc_end": 0.50,
        "root_depth_initial_m": 0.15,
        "root_depth_max_m": 0.90,
        "depletion_fraction_p": 0.50,
        "days_initial": 20,
        "days_development": 30,
        "days_mid": 60,
        "days_late": 25,
        "total_growing_days": 135,
        "reference": "FAO-56 Table 12, Allen et al. (1998)",
    },
    {
        "name": "Sunflower",
        "scientific_name": "Helianthus annuus",
        "crop_type": "oilseed",
        "kc_initial": 0.35,
        "kc_mid": 1.10,
        "kc_end": 0.35,
        "root_depth_initial_m": 0.20,
        "root_depth_max_m": 1.50,
        "depletion_fraction_p": 0.45,
        "days_initial": 25,
        "days_development": 35,
        "days_mid": 45,
        "days_late": 25,
        "total_growing_days": 130,
        "reference": "FAO-56 Table 12, Allen et al. (1998)",
    },
    {
        "name": "Potato",
        "scientific_name": "Solanum tuberosum",
        "crop_type": "vegetable",
        "kc_initial": 0.50,
        "kc_mid": 1.15,
        "kc_end": 0.75,
        "root_depth_initial_m": 0.15,
        "root_depth_max_m": 0.60,
        "depletion_fraction_p": 0.35,
        "days_initial": 25,
        "days_development": 30,
        "days_mid": 30,
        "days_late": 20,
        "total_growing_days": 105,
        "reference": "FAO-56 Table 12, Allen et al. (1998)",
    },
    {
        "name": "Groundnut",
        "scientific_name": "Arachis hypogaea",
        "crop_type": "legume",
        "kc_initial": 0.40,
        "kc_mid": 1.15,
        "kc_end": 0.60,
        "root_depth_initial_m": 0.15,
        "root_depth_max_m": 0.60,
        "depletion_fraction_p": 0.50,
        "days_initial": 25,
        "days_development": 35,
        "days_mid": 45,
        "days_late": 25,
        "total_growing_days": 130,
        "reference": "FAO-56 Table 12, Allen et al. (1998)",
    },
]


# ================================================================== #
# Demo Farm Data
# ================================================================== #

DEMO_FARM = {
    "name": "Autonomous Demo Farm",
    "owner_name": "Demo Farmer",
    "location_description": "Simulated farm for development and testing",
    "latitude": 18.5204,   # Pune, Maharashtra, India (demo coordinates)
    "longitude": 73.8567,
    "altitude_m": 560.0,
    "total_area_ha": 5.0,
    "notes": "Auto-created by Phase 3 seed script. All data is simulated.",
}

DEMO_FIELD = {
    "name": "Main Field",
    "area_ha": 5.0,
    "soil_type": "Sandy Loam",
    "latitude": 18.5204,
    "longitude": 73.8567,
    "notes": "Demo field for testing multi-zone irrigation scheduling.",
}

DEMO_ZONES = [
    {
        "name": "Zone-1 (Wheat Block)",
        "zone_number": 1,
        "area_ha": 2.0,
        "irrigation_method": "drip",
        "max_irrigation_mm": 40.0,
        "min_irrigation_mm": 5.0,
        "is_active": True,
        "crop_name": "Wheat",
    },
    {
        "name": "Zone-2 (Tomato Block)",
        "zone_number": 2,
        "area_ha": 1.5,
        "irrigation_method": "drip",
        "max_irrigation_mm": 30.0,
        "min_irrigation_mm": 5.0,
        "is_active": True,
        "crop_name": "Tomato",
    },
    {
        "name": "Zone-3 (Maize Block)",
        "zone_number": 3,
        "area_ha": 1.5,
        "irrigation_method": "sprinkler",
        "max_irrigation_mm": 50.0,
        "min_irrigation_mm": 10.0,
        "is_active": True,
        "crop_name": "Maize",
    },
]

# Simulated Sandy Loam soil profile (FAO-56 Table 19 reference values).
# Source: Doorenbos & Pruitt (1977); Allen et al. (1998).
DEMO_SOIL = {
    "data_source": "simulated",
    "volumetric_moisture_pct": 22.0,
    "field_capacity_pct": 30.0,
    "wilting_point_pct": 12.0,
    "bulk_density_g_cm3": 1.45,
    "ph": 6.8,
    "organic_matter_pct": 1.2,
    "sand_pct": 65.0,
    "silt_pct": 20.0,
    "clay_pct": 15.0,
    "electrical_conductivity_ds_m": 0.4,
    "depth_cm": 30.0,
    "temperature_c": 26.0,
    "notes": "Simulated Sandy Loam — FAO-56 Table 19 reference values.",
}


# ================================================================== #
# Seed runner
# ================================================================== #

def seed_crops(db) -> int:
    repo = CropRepository(db)
    inserted = 0
    for crop_data in FAO56_CROPS:
        existing = repo.get_by_name(crop_data["name"])
        if existing is None:
            repo.create(**crop_data)
            inserted += 1
            logger.info("  Inserted crop: %s", crop_data["name"])
        else:
            logger.info("  Crop exists, skipping: %s", crop_data["name"])
    return inserted


def seed_demo_farm(db) -> Farm:
    farm_repo = FarmRepository(db)
    existing = farm_repo.get_by_name(DEMO_FARM["name"])
    if existing:
        logger.info("  Demo farm exists, skipping creation.")
        return existing
    farm = farm_repo.create(**DEMO_FARM)
    logger.info("  Created demo farm: id=%d", farm.id)
    return farm


def seed_demo_field(db, farm: Farm) -> Field:
    field_repo = FieldRepository(db)
    existing = field_repo.get_by_farm(farm.id)
    if existing:
        logger.info("  Demo field exists, skipping creation.")
        return existing[0]
    field = field_repo.create(farm_id=farm.id, **DEMO_FIELD)
    logger.info("  Created demo field: id=%d", field.id)
    return field


def seed_demo_zones(db, field: Field) -> list[Zone]:
    zone_repo = ZoneRepository(db)
    soil_repo = SoilProfileRepository(db)
    existing = zone_repo.get_by_field(field.id)
    if existing:
        logger.info("  Demo zones exist, skipping creation.")
        return list(existing)
    zones = []
    for zone_data in DEMO_ZONES:
        zone = zone_repo.create(field_id=field.id, **zone_data)
        soil_repo.create(zone_id=zone.id, **DEMO_SOIL)
        logger.info(
            "  Created zone: %s (id=%d) with soil profile", zone.name, zone.id
        )
        zones.append(zone)
    return zones


def run_seed() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("=" * 55)
    logger.info("Phase 3 — Database Seed")
    logger.info("=" * 55)

    with SessionLocal() as db:
        logger.info("\n[1/4] Seeding FAO-56 crop constants...")
        n = seed_crops(db)
        logger.info("      %d new crops inserted.", n)

        logger.info("\n[2/4] Seeding demo farm...")
        farm = seed_demo_farm(db)

        logger.info("\n[3/4] Seeding demo field...")
        field = seed_demo_field(db, farm)

        logger.info("\n[4/4] Seeding demo zones + soil profiles...")
        zones = seed_demo_zones(db, field)
        logger.info("      %d zones ready.", len(zones))

        db.commit()

    logger.info("\n" + "=" * 55)
    logger.info("Seed complete.")
    logger.info("=" * 55)


if __name__ == "__main__":
    run_seed()

