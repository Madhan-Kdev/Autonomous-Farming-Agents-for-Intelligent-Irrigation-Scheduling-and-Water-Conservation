"""
Pytest configuration and shared fixtures for the Phase 2 test suite.

Sets up required environment variables BEFORE any app module is imported
so that pydantic-settings does not pick up conflicting system env vars.
"""

from __future__ import annotations

import os

# ------------------------------------------------------------------ #
# Set all required environment variables BEFORE importing any app code.
# This prevents pydantic-settings from loading conflicting system vars.
# ------------------------------------------------------------------ #
_TEST_ENV = {
    "DATABASE_URL": "postgresql+psycopg://postgres:FarmAgent2024!@localhost:5432/autonomous_farming",
    "APP_NAME": "Autonomous Farming Agents Test",
    "APP_ENV": "development",
    "DEBUG": "false",
    "APP_VERSION": "0.1.0",
    "DB_ECHO_SQL": "false",
    "DB_POOL_SIZE": "5",
    "DB_MAX_OVERFLOW": "10",
    "GROQ_API_KEY": "test-key",
    "GROQ_MODEL": "llama-3.3-70b-versatile",
    "GROQ_TEMPERATURE": "0.1",
    "GROQ_MAX_TOKENS": "4096",
    "NASA_POWER_BASE_URL": "https://power.larc.nasa.gov/api/temporal/daily/point",
    "NASA_POWER_FORMAT": "JSON",
    "WEATHER_API_KEY": "test-weather-key",
    "OPENWEATHER_BASE_URL": "https://api.openweathermap.org/data/2.5",
    "LOG_LEVEL": "WARNING",
    "LOG_FORMAT": "text",
    "API_V1_PREFIX": "/api/v1",
    "CORS_ORIGINS": '["http://localhost:5173","http://localhost:3000"]',
    "SIMULATION_SEED": "42",
    "DEFAULT_FARM_ZONES": "3",
}

for key, value in _TEST_ENV.items():
    os.environ[key] = value


import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app():
    """Return the FastAPI application instance."""
    from app.main import app as _app
    return _app


@pytest.fixture(scope="session")
def client(app):
    """Return a synchronous TestClient for the FastAPI application."""
    with TestClient(app, raise_server_exceptions=False) as _client:
        yield _client
