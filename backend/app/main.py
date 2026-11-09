"""
Main FastAPI application entry point.

Architecture
------------
This module:
1. Initialises logging at startup.
2. Creates the FastAPI application with full metadata.
3. Registers CORS middleware.
4. Registers exception handlers for the custom exception hierarchy.
5. Mounts all API routers.
6. Provides startup/shutdown lifecycle events.

Start the application::

    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

From the ``backend/`` directory with the virtual environment activated.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router
from app.core.config import settings
from app.core.exceptions import (
    DatabaseConnectionError,
    DataValidationError,
    FarmingAgentError,
    ResourceNotFoundError,
)
from app.core.logging_config import setup_logging

# ------------------------------------------------------------------ #
# Logging — must be configured before any other imports use loggers.
# ------------------------------------------------------------------ #
setup_logging(level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
logger = logging.getLogger(__name__)


# ================================================================== #
# Lifespan
# ================================================================== #


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Startup: verify database connectivity and log configuration summary.
    Shutdown: log clean shutdown.
    """
    # --- Startup ---
    logger.info("=" * 60)
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Environment : %s", settings.APP_ENV)
    logger.info("Debug mode  : %s", settings.DEBUG)
    logger.info("Log level   : %s", settings.LOG_LEVEL)

    # Verify database connectivity (non-fatal — application still starts).
    from app.database.engine import check_database_connection

    db_ok = check_database_connection()
    if db_ok:
        logger.info("Database    : Connected [OK]")
    else:
        logger.warning(
            "Database    : UNREACHABLE [FAIL]  "
            "(Set DATABASE_URL in .env and ensure PostgreSQL is running)"
        )

    logger.info("=" * 60)
    logger.info("Application ready — listening for requests.")

    yield

    # --- Shutdown ---
    logger.info("Shutting down %s.", settings.APP_NAME)


# ================================================================== #
# Application Factory
# ================================================================== #


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns a fully configured app instance with middleware, exception
    handlers, and routers attached.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        description=(
            "Autonomous multi-agent irrigation scheduling and water conservation system. "
            "100% software-based — no physical hardware required."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        openapi_url="/openapi.json" if settings.APP_ENV != "production" else None,
        lifespan=lifespan,
    )

    # ---------------------------------------------------------------- #
    # Middleware
    # ---------------------------------------------------------------- #
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------- #
    # Exception handlers
    # ---------------------------------------------------------------- #

    @app.exception_handler(ResourceNotFoundError)
    async def not_found_handler(
        request: Request, exc: ResourceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=exc.to_dict(),
        )

    @app.exception_handler(DataValidationError)
    async def validation_error_handler(
        request: Request, exc: DataValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=exc.to_dict(),
        )

    @app.exception_handler(DatabaseConnectionError)
    async def db_connection_handler(
        request: Request, exc: DatabaseConnectionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=exc.to_dict(),
        )

    @app.exception_handler(FarmingAgentError)
    async def farming_agent_error_handler(
        request: Request, exc: FarmingAgentError
    ) -> JSONResponse:
        """Catch-all for all application-specific exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Last-resort handler for unexpected exceptions."""
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred.",
                "details": {},
            },
        )

    # ---------------------------------------------------------------- #
    # Routers
    # ---------------------------------------------------------------- #
    app.include_router(router)

    return app


# ================================================================== #
# Application instance
# ================================================================== #

app: FastAPI = create_app()
