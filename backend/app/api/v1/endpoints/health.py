"""
Health check endpoints.

Provides two health endpoints:
* ``GET /api/v1/health`` — basic application health.
* ``GET /api/v1/health/database`` — database connectivity check via SELECT 1.

These endpoints are used by:
* Load balancers and container orchestrators.
* CI/CD pipelines to verify deployment readiness.
* The frontend status indicator.
"""

from __future__ import annotations

import logging
import platform
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.database.engine import check_database_connection
from app.schemas.common import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


# ------------------------------------------------------------------ #
# Response models
# ------------------------------------------------------------------ #


class HealthStatus(BaseModel):
    """Application health status payload."""

    status: str
    app_name: str
    version: str
    environment: str
    python_platform: str
    timestamp: datetime


class DatabaseHealthStatus(BaseModel):
    """Database health status payload."""

    status: str
    database_reachable: bool
    timestamp: datetime
    message: str


# ------------------------------------------------------------------ #
# Endpoints
# ------------------------------------------------------------------ #


@router.get(
    "",
    response_model=APIResponse[HealthStatus],
    summary="Application health check",
    description=(
        "Returns basic application health information. "
        "A 200 response indicates the application is running. "
        "This endpoint does NOT verify database connectivity."
    ),
)
def get_health() -> APIResponse[HealthStatus]:
    """Return application health status."""
    logger.debug("Health check requested.")
    status = HealthStatus(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        python_platform=platform.python_version(),
        timestamp=datetime.now(timezone.utc),
    )
    return APIResponse(
        success=True,
        data=status,
        message="Application is healthy.",
    )


@router.get(
    "/database",
    response_model=APIResponse[DatabaseHealthStatus],
    summary="Database health check",
    description=(
        "Executes ``SELECT 1`` against the configured PostgreSQL database. "
        "Returns 200 with ``database_reachable=true`` if successful, "
        "or 200 with ``database_reachable=false`` if the database is unreachable. "
        "The HTTP status code is always 200 — callers must inspect the payload."
    ),
)
def get_database_health() -> APIResponse[DatabaseHealthStatus]:
    """Return database connectivity status."""
    logger.debug("Database health check requested.")
    reachable = check_database_connection()

    if reachable:
        status = DatabaseHealthStatus(
            status="healthy",
            database_reachable=True,
            timestamp=datetime.now(timezone.utc),
            message="Database is reachable (SELECT 1 succeeded).",
        )
        message = "Database is healthy."
    else:
        status = DatabaseHealthStatus(
            status="degraded",
            database_reachable=False,
            timestamp=datetime.now(timezone.utc),
            message=(
                "Database is unreachable. "
                "Verify DATABASE_URL and that PostgreSQL is running."
            ),
        )
        message = "Database is unreachable."

    return APIResponse(
        success=reachable,
        data=status,
        message=message,
    )
