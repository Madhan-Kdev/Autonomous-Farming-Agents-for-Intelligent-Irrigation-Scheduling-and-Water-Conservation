"""
Phase 16 — REST API Endpoints tests.

Tests cover:
1. Farms & Zones endpoints:
   - GET /api/v1/farms (lists farms with nested fields and zones)
   - GET /api/v1/farms/{id} (retrieves single farm)
   - GET /api/v1/farms/{id} 404 for invalid farm
2. Crops reference endpoints:
   - GET /api/v1/crops (lists FAO-56 seeded crops)
   - GET /api/v1/crops/{crop_name} (details for specific crop)
   - GET /api/v1/crops/{crop_name} 404 for nonexistent crop
3. Agent Orchestration endpoints:
   - POST /api/v1/agents/run (executes full multi-agent workflow over HTTP)
   - POST /api/v1/agents/run 404 for invalid farm
   - GET /api/v1/agents/zones/{zone_id}/history (returns zone irrigation history)
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


class TestFarmsEndpoints:
    def test_list_farms(self, client):
        resp = client.get("/api/v1/farms")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) >= 1
        assert body["data"][0]["name"] == "Autonomous Demo Farm"
        assert len(body["data"][0]["fields"]) >= 1

    def test_get_farm_by_id(self, client):
        # 1. First get farm ID
        farms_resp = client.get("/api/v1/farms")
        farm_id = farms_resp.json()["data"][0]["id"]

        resp = client.get(f"/api/v1/farms/{farm_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["id"] == farm_id

    def test_get_invalid_farm_404(self, client):
        resp = client.get("/api/v1/farms/999999")
        assert resp.status_code == 404


class TestCropsEndpoints:
    def test_list_crops(self, client):
        resp = client.get("/api/v1/crops")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) >= 10
        names = [c["name"] for c in body["data"]]
        assert "Wheat" in names
        assert "Tomato" in names

    def test_get_crop_by_name(self, client):
        resp = client.get("/api/v1/crops/Wheat")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Wheat"
        assert body["data"]["kc_mid"] == 1.15

    def test_get_invalid_crop_404(self, client):
        resp = client.get("/api/v1/crops/NonExistentCropNameXYZ")
        assert resp.status_code == 404


class TestAgentOrchestrationEndpoints:
    def test_run_agent_workflow_via_api(self, client):
        farms_resp = client.get("/api/v1/farms")
        farm_data = farms_resp.json()["data"][0]
        farm_id = farm_data["id"]
        zone_id = farm_data["fields"][0]["zones"][0]["id"]

        payload = {
            "farm_id": farm_id,
            "zone_ids": [zone_id],
            "crop_type": "Wheat",
            "user_notes": "Automated API integration test run",
        }

        resp = client.post("/api/v1/agents/run", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        state = body["data"]

        # Validate multi-agent state payload received over HTTP
        assert state["is_complete"] is True
        assert state["workflow_step"] == "COMPLETED"
        assert state["weather"]["temperature_c"] is not None
        assert state["soil"]["soil_stress_index"] is not None
        assert state["crop"]["crop_coefficient_kc"] is not None
        assert state["et0"]["et0_reference_mm"] is not None
        assert state["irrigation_decision"]["decision"] is not None
        assert state["optimization"]["baseline_volume_mm"] is not None
        assert state["risk"]["overall_risk_level"] is not None
        assert len(state["advisory"]["recommended_action"]) > 0

    def test_run_agent_workflow_invalid_farm_404(self, client):
        payload = {"farm_id": 999999}
        resp = client.post("/api/v1/agents/run", json=payload)
        assert resp.status_code == 404

    def test_get_zone_history(self, client):
        farms_resp = client.get("/api/v1/farms")
        zone_id = farms_resp.json()["data"][0]["fields"][0]["zones"][0]["id"]

        resp = client.get(f"/api/v1/agents/zones/{zone_id}/history?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)

    def test_get_zone_soil_history(self, client):
        farms_resp = client.get("/api/v1/farms")
        zone_id = farms_resp.json()["data"][0]["fields"][0]["zones"][0]["id"]

        resp = client.get(f"/api/v1/agents/zones/{zone_id}/soil-history?limit=15")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
