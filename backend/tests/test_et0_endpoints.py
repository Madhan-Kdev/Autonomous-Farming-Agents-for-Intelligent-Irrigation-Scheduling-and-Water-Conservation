"""
Tests for ET0 & Crop ETc FAO-56 Penman-Monteith Derivation Endpoints.
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://postgres:FarmAgent2024!@localhost:5432/autonomous_farming"
)
os.environ["DEBUG"] = "false"


@pytest.fixture(scope="module")
def client():
    from app.core.config import _reset_settings
    _reset_settings()
    from app.main import app
    with TestClient(app) as c:
        yield c


class TestET0DerivationEndpoints:
    def test_get_et0_derivation_default_farm(self, client):
        resp = client.get("/api/v1/et0/derivation?farm_id=1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["et0_mm"] > 0
        assert data["radiation_term_mm"] >= 0
        assert data["aerodynamic_term_mm"] >= 0
        assert len(data["steps"]) == 13
        assert data["steps"][0]["step_number"] == 1
        assert data["steps"][12]["step_number"] == 13
        assert "T_mean" in data["steps"][0]["fao_equation"]

    def test_get_et0_derivation_with_crop(self, client):
        resp = client.get("/api/v1/et0/derivation?farm_id=1&crop_name=Wheat&growth_stage=mid")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["crop_etc"] is not None
        crop_etc = data["crop_etc"]
        assert crop_etc["crop_name"] == "Wheat"
        assert crop_etc["kc"] > 0
        assert crop_etc["etc_mm"] == round(data["et0_mm"] * crop_etc["kc"], 2)
        assert crop_etc["daily_water_liters_per_ha"] > 0

    def test_get_et0_derivation_invalid_farm_404(self, client):
        resp = client.get("/api/v1/et0/derivation?farm_id=999999")
        assert resp.status_code == 404

    def test_post_custom_et0_calculation(self, client):
        payload = {
            "temp_max_c": 32.5,
            "temp_min_c": 21.0,
            "humidity_max_pct": 80.0,
            "humidity_min_pct": 35.0,
            "wind_speed_m_s": 2.5,
            "solar_radiation_mj_m2": 22.5,
            "altitude_m": 250.0,
            "latitude_deg": 18.5,
            "day_of_year": 180,
            "crop_name": "Wheat",
            "growth_stage": "mid",
        }
        resp = client.post("/api/v1/et0/calculate", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["et0_mm"] > 3.0  # Summer warm conditions produce typical ET0 > 3.0 mm/day
        assert data["crop_etc"] is not None
        assert len(data["steps"]) == 13

