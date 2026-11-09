"""
Tests for the core configuration module.

Tests:
- Settings loads without error given valid environment.
- Required fields are present and correctly typed.
- DATABASE_URL validator rejects non-PostgreSQL URLs.
- LOG_LEVEL validator normalises to uppercase.
- is_production and is_development properties work correctly.
"""

from __future__ import annotations

import os

import pytest


def test_settings_loads():
    """Settings must load without raising an exception."""
    from app.core.config import settings
    assert settings is not None


def test_app_name_is_set():
    """APP_NAME must be a non-empty string."""
    from app.core.config import settings
    assert isinstance(settings.APP_NAME, str)
    assert len(settings.APP_NAME) > 0


def test_database_url_is_postgresql():
    """DATABASE_URL must start with 'postgresql'."""
    from app.core.config import settings
    assert settings.DATABASE_URL.startswith("postgresql")


def test_log_level_is_uppercase():
    """LOG_LEVEL must be normalised to uppercase."""
    from app.core.config import settings
    assert settings.LOG_LEVEL == settings.LOG_LEVEL.upper()


def test_valid_log_levels():
    """LOG_LEVEL must be one of the accepted values."""
    from app.core.config import settings
    valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    assert settings.LOG_LEVEL in valid


def test_is_development_property():
    """is_development must return True when APP_ENV is 'development'."""
    from app.core.config import Settings
    s = Settings(
        APP_ENV="development",
        DATABASE_URL="postgresql+psycopg://u:p@h:5432/db",
    )
    assert s.is_development is True
    assert s.is_production is False


def test_is_production_property():
    """is_production must return True when APP_ENV is 'production'."""
    from app.core.config import Settings
    s = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql+psycopg://u:p@h:5432/db",
    )
    assert s.is_production is True
    assert s.is_development is False


def test_invalid_database_url_raises():
    """DATABASE_URL that does not start with 'postgresql' must raise ValueError."""
    from pydantic import ValidationError
    from app.core.config import Settings
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="sqlite:///test.db")


def test_groq_temperature_range():
    """GROQ_TEMPERATURE must be between 0 and 2."""
    from app.core.config import settings
    assert 0.0 <= settings.GROQ_TEMPERATURE <= 2.0


def test_db_pool_size_is_positive():
    """DB_POOL_SIZE must be >= 1."""
    from app.core.config import settings
    assert settings.DB_POOL_SIZE >= 1


def test_api_v1_prefix():
    """API_V1_PREFIX must be /api/v1."""
    from app.core.config import settings
    assert settings.API_V1_PREFIX == "/api/v1"
