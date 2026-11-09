"""
Phase 3 database and model tests.

Tests:
- Database is reachable with the configured URL.
- All 11 tables exist after migration.
- ORM models can be instantiated.
- Repository CRUD operations work.
- Seed data is present (crops, farm, zones).
- FAO-56 Kc values are within valid ranges.
- IrrigationRecord and ET0Record can be created.
"""

from __future__ import annotations

import os
import pytest

# Use real DB for Phase 3 tests (not mocked).
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://postgres:FarmAgent2024!@localhost:5432/autonomous_farming"
)
os.environ["DEBUG"] = "false"


@pytest.fixture(scope="module")
def db():
    """Provide a real database session for Phase 3 tests."""
    from app.core.config import _reset_settings
    _reset_settings()
    from app.database.engine import SessionLocal
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


# ================================================================== #
# Database connectivity
# ================================================================== #

def test_database_is_reachable():
    """Database must be reachable from the Python application."""
    from app.core.config import _reset_settings
    _reset_settings()
    from app.database.engine import check_database_connection
    assert check_database_connection() is True


# ================================================================== #
# Table existence
# ================================================================== #

def test_all_tables_exist(db):
    """All 11 Phase 3 tables must exist in the database."""
    from sqlalchemy import inspect
    inspector = inspect(db.bind)
    tables = set(inspector.get_table_names())
    required = {
        "farms", "fields", "zones", "soil_profiles",
        "crops", "crop_growth_stages",
        "weather_records", "et0_records",
        "irrigation_records",
        "agent_execution_logs",
        "alembic_version",
    }
    missing = required - tables
    assert missing == set(), f"Missing tables: {missing}"


# ================================================================== #
# Crop data (FAO-56)
# ================================================================== #

def test_crops_seeded(db):
    """10 FAO-56 crops must be present after seeding."""
    from app.repositories.repositories import CropRepository
    repo = CropRepository(db)
    assert repo.count() >= 10


def test_wheat_kc_values(db):
    """Wheat Kc values must match FAO-56 Table 12."""
    from app.repositories.repositories import CropRepository
    repo = CropRepository(db)
    wheat = repo.get_by_name("Wheat")
    assert wheat is not None
    assert wheat.kc_initial == pytest.approx(0.3, abs=0.01)
    assert wheat.kc_mid == pytest.approx(1.15, abs=0.01)
    assert wheat.kc_end == pytest.approx(0.25, abs=0.01)


def test_all_kc_values_in_valid_range(db):
    """All crop Kc values must be within 0.1–1.35 (FAO-56 range)."""
    from app.repositories.repositories import CropRepository
    repo = CropRepository(db)
    crops = repo.get_all_crops()
    for crop in crops:
        assert 0.1 <= crop.kc_initial <= 1.35, f"{crop.name} kc_initial out of range"
        assert 0.1 <= crop.kc_mid <= 1.35, f"{crop.name} kc_mid out of range"
        assert 0.1 <= crop.kc_end <= 1.35, f"{crop.name} kc_end out of range"


def test_depletion_fraction_in_range(db):
    """FAO-56 depletion fraction p must be between 0.1 and 0.8."""
    from app.repositories.repositories import CropRepository
    repo = CropRepository(db)
    for crop in repo.get_all_crops():
        assert 0.1 <= crop.depletion_fraction_p <= 0.8, (
            f"{crop.name} depletion_fraction_p={crop.depletion_fraction_p} out of range"
        )


# ================================================================== #
# Farm / Field / Zone
# ================================================================== #

def test_demo_farm_exists(db):
    """Demo farm must be present after seeding."""
    from app.repositories.repositories import FarmRepository
    repo = FarmRepository(db)
    farm = repo.get_by_name("Autonomous Demo Farm")
    assert farm is not None
    assert farm.latitude == pytest.approx(18.5204, abs=0.001)
    assert farm.longitude == pytest.approx(73.8567, abs=0.001)


def test_demo_field_exists(db):
    """Demo field must be linked to the demo farm."""
    from app.repositories.repositories import FarmRepository, FieldRepository
    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    fields = FieldRepository(db).get_by_farm(farm.id)
    assert len(fields) >= 1
    assert fields[0].area_ha == pytest.approx(5.0, abs=0.01)


def test_three_zones_exist(db):
    """Demo field must have exactly 3 active zones."""
    from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zones = ZoneRepository(db).get_active_zones(field.id)
    assert len(zones) == 3


def test_zone_numbers_sequential(db):
    """Zone numbers must be 1, 2, 3 in order."""
    from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zones = ZoneRepository(db).get_active_zones(field.id)
    numbers = [z.zone_number for z in zones]
    assert numbers == [1, 2, 3]


# ================================================================== #
# Soil profiles
# ================================================================== #

def test_each_zone_has_soil_profile(db):
    """Each of the 3 zones must have at least 1 soil profile."""
    from app.repositories.repositories import (
        FarmRepository, FieldRepository, SoilProfileRepository, ZoneRepository,
    )
    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zones = ZoneRepository(db).get_active_zones(field.id)
    soil_repo = SoilProfileRepository(db)
    for zone in zones:
        profile = soil_repo.get_latest_for_zone(zone.id)
        assert profile is not None, f"Zone {zone.name} has no soil profile"
        assert profile.data_source == "simulated"


def test_soil_moisture_within_field_capacity(db):
    """Volumetric moisture must be between wilting point and field capacity."""
    from app.repositories.repositories import (
        FarmRepository, FieldRepository, SoilProfileRepository, ZoneRepository,
    )
    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zones = ZoneRepository(db).get_active_zones(field.id)
    soil_repo = SoilProfileRepository(db)
    for zone in zones:
        profile = soil_repo.get_latest_for_zone(zone.id)
        assert profile.wilting_point_pct < profile.volumetric_moisture_pct
        assert profile.volumetric_moisture_pct <= profile.field_capacity_pct


# ================================================================== #
# Repository CRUD
# ================================================================== #

def test_farm_create_and_delete(db):
    """FarmRepository must create and delete a farm."""
    from app.repositories.repositories import FarmRepository
    repo = FarmRepository(db)
    farm = repo.create(
        name="Test Farm CRUD",
        latitude=20.0,
        longitude=80.0,
    )
    assert farm.id is not None
    deleted = repo.delete(farm.id)
    assert deleted is True
    assert repo.get_by_id(farm.id) is None
    db.rollback()  # clean up


def test_irrigation_record_created(db):
    """IrrigationRecord can be inserted and retrieved."""
    from datetime import datetime, timezone
    from app.repositories.repositories import (
        FarmRepository, FieldRepository, IrrigationRecordRepository, ZoneRepository,
    )
    farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
    field = FieldRepository(db).get_by_farm(farm.id)[0]
    zone = ZoneRepository(db).get_active_zones(field.id)[0]

    repo = IrrigationRecordRepository(db)
    record = repo.create(
        zone_id=zone.id,
        farm_id=farm.id,
        scheduled_at=datetime.now(timezone.utc),
        decision="REQUIRED",
        recommended_volume_mm=15.0,
        was_applied=False,
        decision_confidence=0.88,
    )
    assert record.id is not None
    assert record.decision == "REQUIRED"

    # Clean up
    repo.delete(record.id)
    db.rollback()

