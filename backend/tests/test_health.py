"""
Tests for the health check endpoints.

Tests:
- GET /api/v1/health returns 200 with structured payload.
- GET /api/v1/health/database returns 200 with DB status payload.
"""

from __future__ import annotations


def test_health_endpoint_returns_200(client):
    """Basic health endpoint must return HTTP 200."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_endpoint_structure(client):
    """Health endpoint payload must have required keys."""
    response = client.get("/api/v1/health")
    data = response.json()

    assert "success" in data
    assert "data" in data
    assert "message" in data
    assert "timestamp" in data
    assert data["success"] is True


def test_health_endpoint_app_name(client):
    """Health endpoint must return the configured app name."""
    response = client.get("/api/v1/health")
    data = response.json()
    assert "Farming" in data["data"]["app_name"]


def test_health_endpoint_environment(client):
    """Health endpoint must return a valid environment name."""
    response = client.get("/api/v1/health")
    data = response.json()
    assert data["data"]["environment"] in {"development", "staging", "production"}


def test_health_endpoint_version(client):
    """Health endpoint must return a version string."""
    response = client.get("/api/v1/health")
    data = response.json()
    version = data["data"]["version"]
    assert isinstance(version, str)
    assert len(version) > 0


def test_database_health_endpoint_returns_200(client):
    """Database health endpoint must always return HTTP 200."""
    response = client.get("/api/v1/health/database")
    assert response.status_code == 200


def test_database_health_endpoint_structure(client):
    """Database health endpoint payload must have required keys."""
    response = client.get("/api/v1/health/database")
    data = response.json()

    assert "success" in data
    assert "data" in data
    assert "timestamp" in data
    assert "database_reachable" in data["data"]
    assert "status" in data["data"]
    assert "message" in data["data"]


def test_database_health_reachable_is_bool(client):
    """database_reachable must be a boolean value."""
    response = client.get("/api/v1/health/database")
    data = response.json()
    assert isinstance(data["data"]["database_reachable"], bool)
