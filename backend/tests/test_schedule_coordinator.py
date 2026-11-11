"""
Tests for FarmScheduleCoordinator and GET /api/v1/farms/{farm_id}/schedule.
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from app.schemas.agent_state import IrrigationPriority, ZoneIrrigationPlan
from app.service.schedule_coordinator import FarmScheduleCoordinator

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


class TestFarmScheduleCoordinator:
    """Unit tests for the schedule deconfliction engine."""

    def test_single_zone_schedule(self):
        coordinator = FarmScheduleCoordinator(pump_capacity_l_h=50000.0, irrigation_start_hour=6)
        plans = [
            ZoneIrrigationPlan(
                zone_id=1,
                zone_name="Zone 1",
                irrigation_required=True,
                recommended_volume_mm=10.0,
                priority=IrrigationPriority.HIGH,
                area_ha=1.0,
                flow_rate_l_h=25000.0,
            )
        ]
        summary = coordinator.coordinate(plans)
        assert summary.zones_requiring_irrigation == 1
        assert summary.total_farm_volume_liters == 100000.0  # 10mm * 1ha * 10,000
        assert summary.total_pumping_duration_minutes == 240.0  # 100,000L / 25,000 L/h * 60 = 240 min
        assert summary.conflicts_resolved == 0
        assert summary.scheduled_zones[0].start_time == "06:00"
        assert summary.scheduled_zones[0].end_time == "10:00"

    def test_multi_zone_staggered_deconfliction(self):
        """Two zones requiring irrigation must be scheduled sequentially."""
        coordinator = FarmScheduleCoordinator(pump_capacity_l_h=50000.0, irrigation_start_hour=6)
        plans = [
            ZoneIrrigationPlan(
                zone_id=1,
                zone_name="Zone 1",
                irrigation_required=True,
                recommended_volume_mm=10.0,
                priority=IrrigationPriority.MEDIUM,
                area_ha=0.5,
                flow_rate_l_h=25000.0,
            ),
            ZoneIrrigationPlan(
                zone_id=2,
                zone_name="Zone 2",
                irrigation_required=True,
                recommended_volume_mm=15.0,
                priority=IrrigationPriority.CRITICAL,  # higher priority should be first!
                area_ha=0.5,
                flow_rate_l_h=25000.0,
            ),
        ]
        summary = coordinator.coordinate(plans)
        assert summary.zones_requiring_irrigation == 2
        assert summary.conflicts_resolved == 1

        # Zone 2 is CRITICAL -> must be sequence 1
        first = summary.scheduled_zones[0]
        assert first.zone_id == 2
        assert first.sequence_order == 1
        assert first.start_time == "06:00"

        # Zone 1 is MEDIUM -> must start exactly when Zone 2 ends
        second = summary.scheduled_zones[1]
        assert second.zone_id == 1
        assert second.sequence_order == 2
        assert second.start_time == first.end_time
        assert second.conflict_detected is True

    def test_water_budget_rationing(self):
        """When total demand exceeds budget, lower priority zones must be scaled/deferred."""
        coordinator = FarmScheduleCoordinator(
            water_budget_liters=60000.0,  # Only 60k L available
        )
        plans = [
            ZoneIrrigationPlan(
                zone_id=1,
                zone_name="Zone 1 - Critical",
                irrigation_required=True,
                recommended_volume_mm=10.0,
                priority=IrrigationPriority.CRITICAL,
                area_ha=0.5,  # 50,000 L
            ),
            ZoneIrrigationPlan(
                zone_id=2,
                zone_name="Zone 2 - Low",
                irrigation_required=True,
                recommended_volume_mm=10.0,
                priority=IrrigationPriority.LOW,
                area_ha=0.5,  # 50,000 L -> total requested 100k > 60k budget
            ),
        ]
        summary = coordinator.coordinate(plans)
        assert summary.rationing_applied is True
        # Critical gets full 50,000 L
        crit_zone = [z for z in summary.scheduled_zones if z.zone_id == 1][0]
        assert crit_zone.volume_liters == 50000.0

        # Low priority gets scaled down to remaining 10,000 L
        low_zone = [z for z in summary.scheduled_zones if z.zone_id == 2][0]
        assert low_zone.volume_liters == 10000.0
        assert low_zone.rationing_applied is True


class TestFarmScheduleEndpoint:
    """Integration test for GET /api/v1/farms/{farm_id}/schedule."""

    def test_get_farm_schedule_success(self, client: TestClient):
        resp = client.get("/api/v1/farms/1/schedule")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        data = body["data"]

        assert data["farm_id"] == 1
        assert "scheduled_zones" in data
        assert len(data["scheduled_zones"]) > 0
        assert data["pump_capacity_l_h"] == 50000.0
        for z in data["scheduled_zones"]:
            assert "start_time" in z
            assert "end_time" in z
            assert "duration_minutes" in z

    def test_get_farm_schedule_farm_not_found(self, client: TestClient):
        resp = client.get("/api/v1/farms/99999/schedule")
        assert resp.status_code == 404
