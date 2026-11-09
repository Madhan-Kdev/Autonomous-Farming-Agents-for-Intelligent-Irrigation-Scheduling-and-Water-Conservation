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

