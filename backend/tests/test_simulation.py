"""
Phase 17 — Autonomous Simulation & Virtual IoT Telemetry Generator tests.

Tests cover:
1. VirtualFarmSimulator daily advance:
   - Weather record generation (solar radiation, temperature, humidity, wind).
   - Soil moisture update per zone with ETc depletion and irrigation replenishment.
   - Rain event simulation and drydown dynamics.
2. Advance simulation API endpoint:
   - POST /api/v1/simulation/advance
   - Parameter validation and 404 for invalid farm.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://postgres:FarmAgent2024!@localhost:5432/autonomous_farming"
)
os.environ["DEBUG"] = "false"


@pytest.fixture(scope="module")
def db():
    from app.core.config import _reset_settings
    _reset_settings()
    from app.database.engine import SessionLocal
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="module")
def client():
    from app.core.config import _reset_settings
    _reset_settings()
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module", autouse=True)
def cleanup_simulation_artifacts():
    yield
    from app.database.engine import SessionLocal
    from app.models.zone import SoilProfile
    from app.models.weather import WeatherRecord
    from app.models.irrigation import IrrigationRecord
    session = SessionLocal()
    session.query(SoilProfile).filter(SoilProfile.notes.like("%Simulated daily telemetry update%")).delete(synchronize_session=False)
    session.query(SoilProfile).filter(SoilProfile.notes.like("%Manual irrigation applied%")).delete(synchronize_session=False)
    session.query(WeatherRecord).filter(WeatherRecord.source == "simulated").delete(synchronize_session=False)
    session.query(IrrigationRecord).filter(IrrigationRecord.decision == "MANUAL_COMMAND").delete(synchronize_session=False)
    session.commit()
    session.close()


class TestVirtualFarmSimulator:
    def test_simulator_advances_day_and_creates_records(self, db):
        from app.repositories.repositories import FarmRepository, SoilProfileRepository, WeatherRecordRepository
        from app.service.simulator import VirtualFarmSimulator

        farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
        sim = VirtualFarmSimulator(db, seed=123)

        target_d = date(2026, 10, 15)
        res = sim.advance_day(
            farm_id=farm.id,
            target_date=target_d,
            irrigation_events={},
            force_rain_mm=0.0,
        )

        assert res.target_date == target_d
        assert res.weather_record_id is not None
        assert len(res.soil_profiles_updated) >= 1
        assert res.simulated_et0_mm > 0.0

        # Verify DB records
        w_rec = WeatherRecordRepository(db).get_for_date(farm.id, target_d)
        assert w_rec is not None
        assert w_rec.source == "simulated"

    def test_simulator_irrigation_replenishes_soil_moisture(self, db):
        from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
        from app.service.simulator import VirtualFarmSimulator

        farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
        field = FieldRepository(db).get_by_farm(farm.id)[0]
        zone = ZoneRepository(db).get_active_zones(field.id)[0]

        sim = VirtualFarmSimulator(db, seed=999)
        day1 = date(2026, 11, 1)
        day2 = date(2026, 11, 2)

        # Day 1: No rain, no irrigation -> moisture should deplete
        res1 = sim.advance_day(farm.id, target_date=day1, force_rain_mm=0.0)
        moisture1 = res1.zone_moisture_levels[zone.id]

        # Day 2: Apply 30 mm irrigation -> moisture should increase
        res2 = sim.advance_day(
            farm.id,
            target_date=day2,
            irrigation_events={zone.id: 30.0},
            force_rain_mm=0.0,
        )
        moisture2 = res2.zone_moisture_levels[zone.id]

        assert moisture2 > moisture1

    def test_apply_zone_manual_irrigation_replenishes_and_records(self, db):
        from app.repositories.repositories import FarmRepository, FieldRepository, IrrigationRecordRepository, ZoneRepository
        from app.service.simulator import VirtualFarmSimulator

        farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
        field = FieldRepository(db).get_by_farm(farm.id)[0]
        zone = ZoneRepository(db).get_active_zones(field.id)[0]

        sim = VirtualFarmSimulator(db)
        res = sim.apply_zone_manual_irrigation(
            zone_id=zone.id,
            volume_mm=15.0,
            irrigation_method="drip",
        )

        assert res.zone_id == zone.id
        assert res.volume_applied_mm == 15.0
        assert res.volume_applied_liters > 0.0
        assert res.duration_minutes > 0.0
        assert res.soil_moisture_after_pct >= res.soil_moisture_before_pct
        assert res.stress_index_after <= res.stress_index_before
        assert res.irrigation_record_id is not None
        assert res.soil_profile_id is not None

        rec = IrrigationRecordRepository(db).get_by_id(res.irrigation_record_id)
        assert rec is not None
        assert rec.was_applied is True
        assert rec.decision == "MANUAL_COMMAND"
        assert rec.actual_volume_mm == 15.0

    def test_apply_zone_manual_irrigation_deep_percolation(self, db):
        from app.repositories.repositories import FarmRepository, FieldRepository, ZoneRepository
        from app.service.simulator import VirtualFarmSimulator

        farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
        field = FieldRepository(db).get_by_farm(farm.id)[0]
        zone = ZoneRepository(db).get_active_zones(field.id)[0]

        sim = VirtualFarmSimulator(db)
        res = sim.apply_zone_manual_irrigation(
            zone_id=zone.id,
            volume_mm=120.0,
            irrigation_method="flood",
        )

        assert res.deep_percolation_mm > 0.0
        assert res.soil_moisture_after_pct <= round(res.field_capacity_pct, 2)


class TestSimulationEndpoints:
    def test_post_advance_simulation_endpoint(self, client):
        farms_resp = client.get("/api/v1/farms")
        farm_id = farms_resp.json()["data"][0]["id"]
        zone_id = farms_resp.json()["data"][0]["fields"][0]["zones"][0]["id"]

        payload = {
            "farm_id": farm_id,
            "target_date": "2026-12-05",
            "irrigation_events": {str(zone_id): 15.0},
            "force_rain_mm": 5.0,
        }

        resp = client.post("/api/v1/simulation/advance", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["target_date"] == "2026-12-05"
        assert body["data"]["simulated_rain_mm"] == 5.0
        assert len(body["data"]["soil_profiles_updated"]) >= 1

    def test_post_advance_simulation_invalid_farm_404(self, client):
        payload = {"farm_id": 999999}
        resp = client.post("/api/v1/simulation/advance", json=payload)
        assert resp.status_code == 404

    def test_post_irrigate_manual_endpoint(self, client):
        farms_resp = client.get("/api/v1/farms")
        zone_id = farms_resp.json()["data"][0]["fields"][0]["zones"][0]["id"]

        payload = {
            "zone_id": zone_id,
            "volume_mm": 12.5,
            "irrigation_method": "sprinkler",
            "flow_rate_l_h": 20000.0,
        }

        resp = client.post("/api/v1/simulation/irrigate-manual", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["zone_id"] == zone_id
        assert data["volume_applied_mm"] == 12.5
        assert data["irrigation_method"] == "sprinkler"
        assert data["flow_rate_l_h"] == 20000.0
        assert data["duration_minutes"] > 0
        assert data["soil_moisture_after_pct"] >= data["soil_moisture_before_pct"]
        assert data["irrigation_record_id"] > 0

    def test_post_irrigate_manual_endpoint_invalid_zone_400(self, client):
        payload = {
            "zone_id": 999999,
            "volume_mm": 10.0,
        }
        resp = client.post("/api/v1/simulation/irrigate-manual", json=payload)
        assert resp.status_code == 400


