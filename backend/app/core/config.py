"""
Core configuration for the Autonomous Farming Agents backend.

Loads all configuration from environment variables using Pydantic Settings.
Provides a singleton `settings` object used throughout the application.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.

    All values are validated at startup. Missing required variables will
    raise a clear error rather than causing silent failures at runtime.
    """

    model_config = SettingsConfigDict(
        # Search for .env in backend dir first, then project root.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    APP_NAME: str = Field(
        default="Autonomous Farming Agents",
        description="Human-readable application name.",
    )
    APP_ENV: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment.",
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode.  Must be False in production.",
    )
    APP_VERSION: str = Field(
        default="0.1.0",
        description="Semantic version of the application.",
    )

    @field_validator("DEBUG", mode="before")
    @classmethod
    def coerce_debug(cls, v: object) -> bool:
        """
        Coerce the DEBUG env var to a Python bool.

        The standard boolean strings (true/false/1/0/yes/no/on/off) are
        handled by Pydantic.  Any other value (e.g. ``release``, ``debug``,
        a version string) is treated as ``False`` rather than raising an
        error, because the DEBUG env var may be set by the OS or IDE with
        a non-boolean value.
        """
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            normalised = v.strip().lower()
            if normalised in {"true", "1", "yes", "on"}:
                return True
            return False  # Any unrecognised string → False (safe default)
        return bool(v)

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:FarmAgent2024!@localhost:5432/autonomous_farming",
        description=(
            "Full PostgreSQL connection string.  "
            "Example: postgresql+psycopg://user:pass@host:5432/db"
        ),
    )
    DB_ECHO_SQL: bool = Field(
        default=False,
        description="Log every SQL statement.  Enable only for debugging.",
    )
    DB_POOL_SIZE: int = Field(
        default=5,
        ge=1,
        le=50,
        description="SQLAlchemy connection-pool size.",
    )
    DB_MAX_OVERFLOW: int = Field(
        default=10,
        ge=0,
        le=100,
        description="SQLAlchemy max pool overflow.",
    )

    # ------------------------------------------------------------------ #
    # LLM / Groq
    # ------------------------------------------------------------------ #
    GROQ_API_KEY: str = Field(
        default="",
        description="Groq API key for LLM inference.",
    )
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model identifier.",
    )
    GROQ_TEMPERATURE: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="LLM sampling temperature (lower = more deterministic).",
    )
    GROQ_MAX_TOKENS: int = Field(
        default=4096,
        ge=128,
        description="Maximum tokens per LLM response.",
    )

    # ------------------------------------------------------------------ #
    # NASA POWER
    # ------------------------------------------------------------------ #
    NASA_POWER_BASE_URL: str = Field(
        default="https://power.larc.nasa.gov/api/temporal/daily/point",
        description="NASA POWER API base URL for daily point data.",
    )
    NASA_POWER_FORMAT: str = Field(
        default="JSON",
        description="Preferred response format from NASA POWER.",
    )

    # ------------------------------------------------------------------ #
    # OpenWeatherMap
    # ------------------------------------------------------------------ #
    WEATHER_API_KEY: str = Field(
        default="",
        description="OpenWeatherMap API key.",
    )
    OPENWEATHER_BASE_URL: str = Field(
        default="https://api.openweathermap.org/data/2.5",
        description="OpenWeatherMap API base URL.",
    )

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Root log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )
    LOG_FORMAT: Literal["json", "text"] = Field(
        default="text",
        description="Log output format.  Use 'json' in production.",
    )

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    API_V1_PREFIX: str = Field(
        default="/api/v1",
        description="URL prefix for API version 1.",
    )
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins (frontend URLs).",
    )

    # ------------------------------------------------------------------ #
    # Simulation
    # ------------------------------------------------------------------ #
    SIMULATION_SEED: int = Field(
        default=42,
        description="Random seed for reproducible digital-twin simulations.",
    )
    DEFAULT_FARM_ZONES: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Default number of simulated farm zones.",
    )

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL connection string "
                "(e.g. postgresql+psycopg://...)."
            )
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}, got '{v}'.")
        return upper

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #
    @property
    def is_production(self) -> bool:
        """Return True only when running in the production environment."""
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Return True when running in the development environment."""
        return self.APP_ENV == "development"


@lru_cache(maxsize=1)
def _get_cached_settings() -> Settings:
    """Internal cached factory — use ``get_settings()`` externally."""
    return Settings()


def get_settings() -> Settings:
    """
    Return the (lazily cached) application settings singleton.

    The first call constructs ``Settings()`` and caches it.  Subsequent
    calls return the cached instance without re-reading the environment.

    Call ``_reset_settings()`` in tests after changing env vars to force
    a fresh ``Settings()`` instance with the new values.
    """
    return _get_cached_settings()


def _reset_settings() -> None:
    """Clear the settings cache (for use in tests only)."""
    _get_cached_settings.cache_clear()


class _LazySettings:
    """
    Lazy proxy that forwards attribute access to the cached Settings instance.

    This avoids constructing ``Settings()`` at module import time,
    which would prevent test conftest from injecting environment variables
    before the Settings object is created.
    """

    def __getattr__(self, name: str):  # type: ignore[override]
        return getattr(get_settings(), name)

    def __repr__(self) -> str:
        return repr(get_settings())


# Module-level alias.  Accessing any attribute triggers get_settings() lazily.
settings: Settings = _LazySettings()  # type: ignore[assignment]
