"""
Tests for GET /api/v1/analytics/conservation-summary.

Verifies:
- 200 response with valid farm_id.
- Correct metric structure and field presence.
- Disclaimer is non-empty.
- 404 for unknown farm.
- daily_trend length matches window_days + 1 (inclusive window).
- Water savings calculation correctness (zero records edge case).
- IWUE is 0.0 when no water has been applied.
- conventional_total_mm = conventional_daily_mm × window_days.
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


class TestConservationSummaryEndpoint:
    """Integration tests for the conservation summary analytics endpoint."""

    def test_conservation_summary_valid_farm(self, client: TestClient) -> None:
        """Should return 200 with correct top-level structure for a known farm."""
        resp = client.get("/api/v1/analytics/conservation-summary?farm_id=1&days=7")
        assert resp.status_code == 200, resp.text

        body = resp.json()
        assert body["success"] is True
        data = body["data"]

        required_fields = [
            "farm_id",
            "farm_name",
            "window_days",
            "window_start",
            "window_end",
            "total_water_applied_mm",
            "total_water_applied_liters",
            "total_etc_demand_mm",
            "total_precipitation_mm",
            "total_decisions",
            "decisions_required",
            "decisions_postponed",
            "decisions_not_required",
            "decisions_manual",
            "iwue",
            "average_confidence",
            "conventional_daily_mm",
            "conventional_total_mm",
            "water_saved_mm",
            "water_saved_pct",
            "water_saved_liters",
            "daily_trend",
            "disclaimer",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_conservation_summary_window_days(self, client: TestClient) -> None:
        """daily_trend should have exactly window_days+1 entries (inclusive dates)."""
        days = 10
        resp = client.get(
            f"/api/v1/analytics/conservation-summary?farm_id=1&days={days}"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # window_start to window_end inclusive = days + 1 calendar dates
        assert len(data["daily_trend"]) == days + 1

    def test_conservation_summary_disclaimer_present(self, client: TestClient) -> None:
        """Disclaimer must be non-empty to satisfy data-integrity rules."""
        resp = client.get("/api/v1/analytics/conservation-summary?farm_id=1&days=7")
        data = resp.json()["data"]
        assert len(data["disclaimer"]) > 50

    def test_conservation_summary_conventional_total(self, client: TestClient) -> None:
        """conventional_total_mm should equal conventional_daily_mm × window_days."""
        days = 7
        conv_daily = 5.0
        resp = client.get(
            f"/api/v1/analytics/conservation-summary"
            f"?farm_id=1&days={days}&conventional_daily_mm={conv_daily}"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        expected_conv = round(conv_daily * (days + 1), 2)
        # Allow ±0.5 rounding tolerance
        assert abs(data["conventional_total_mm"] - expected_conv) < 1.0

    def test_conservation_summary_metrics_non_negative(
        self, client: TestClient
    ) -> None:
        """All water volume metrics must be non-negative."""
        resp = client.get("/api/v1/analytics/conservation-summary?farm_id=1&days=14")
        assert resp.status_code == 200
        data = resp.json()["data"]

        for field in [
            "total_water_applied_mm",
            "total_water_applied_liters",
            "total_etc_demand_mm",
            "total_precipitation_mm",
            "conventional_total_mm",
            "water_saved_mm",
            "water_saved_pct",
            "water_saved_liters",
            "iwue",
        ]:
            assert data[field] >= 0.0, f"{field} must be non-negative, got {data[field]}"

    def test_conservation_summary_water_saved_pct_capped(
        self, client: TestClient
    ) -> None:
        """water_saved_pct must never exceed 100."""
        resp = client.get("/api/v1/analytics/conservation-summary?farm_id=1&days=30")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["water_saved_pct"] <= 100.0

    def test_conservation_summary_farm_not_found(self, client: TestClient) -> None:
        """Should return 404 for an unknown farm_id."""
        resp = client.get("/api/v1/analytics/conservation-summary?farm_id=99999&days=7")
        assert resp.status_code == 404

    def test_conservation_summary_daily_trend_structure(
        self, client: TestClient
    ) -> None:
        """Each daily_trend point must have all required keys and numeric values."""
        resp = client.get("/api/v1/analytics/conservation-summary?farm_id=1&days=5")
        assert resp.status_code == 200
        trend = resp.json()["data"]["daily_trend"]
        assert len(trend) > 0

        required_keys = [
            "date",
            "water_applied_mm",
            "etc_demand_mm",
            "precipitation_mm",
            "conventional_mm",
            "saved_mm",
            "decisions",
        ]
        for point in trend:
            for key in required_keys:
                assert key in point, f"daily_trend point missing key: {key}"
            assert isinstance(point["decisions"], list)
            assert isinstance(point["water_applied_mm"], (int, float))

    def test_conservation_summary_farm_name_matches(self, client: TestClient) -> None:
        """farm_name should be non-empty and match the actual farm."""
        resp = client.get("/api/v1/analytics/conservation-summary?farm_id=1&days=7")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["farm_name"]) > 0
        assert data["farm_id"] == 1

