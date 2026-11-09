"""
Custom exception hierarchy for the Autonomous Farming Agents backend.

All application-specific exceptions derive from ``FarmingAgentError`` so that
they can be caught uniformly.  FastAPI exception handlers are registered in
``app/main.py``.
"""

from __future__ import annotations

from typing import Any


# ------------------------------------------------------------------ #
# Base
# ------------------------------------------------------------------ #


class FarmingAgentError(Exception):
    """
    Base class for all Autonomous Farming Agents exceptions.

    Attributes
    ----------
    message:
        Human-readable description of the error.
    details:
        Optional structured context (e.g. field name, received value).
    status_code:
        Suggested HTTP status code for API responses.
    """

    status_code: int = 500

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize the exception to a dict suitable for an API response."""
        return {
            "error": type(self).__name__,
            "message": self.message,
            "details": self.details,
        }


# ------------------------------------------------------------------ #
# Configuration
# ------------------------------------------------------------------ #


class ConfigurationError(FarmingAgentError):
    """Raised when the application configuration is invalid or incomplete."""

    status_code = 500


# ------------------------------------------------------------------ #
# Database
# ------------------------------------------------------------------ #


class DatabaseError(FarmingAgentError):
    """Raised when a database operation fails unexpectedly."""

    status_code = 503


class DatabaseConnectionError(DatabaseError):
    """Raised when the application cannot connect to the database."""

    status_code = 503


# ------------------------------------------------------------------ #
# Agent
# ------------------------------------------------------------------ #


class AgentError(FarmingAgentError):
    """Base class for agent-specific errors."""

    status_code = 500


class AgentTimeoutError(AgentError):
    """Raised when an agent exceeds its allowed execution time."""

    status_code = 504


class AgentStateError(AgentError):
    """
    Raised when the shared agent state is invalid, missing required fields,
    or contains conflicting information.
    """

    status_code = 422


class AgentConfigurationError(AgentError):
    """Raised when an agent is misconfigured at initialisation time."""

    status_code = 500


# ------------------------------------------------------------------ #
# Orchestration
# ------------------------------------------------------------------ #


class OrchestratorError(FarmingAgentError):
    """Raised when the Master Orchestrator encounters an unrecoverable error."""

    status_code = 500


class WorkflowError(FarmingAgentError):
    """Raised when a LangGraph workflow transitions to an invalid state."""

    status_code = 500


# ------------------------------------------------------------------ #
# External Services
# ------------------------------------------------------------------ #


class ExternalServiceError(FarmingAgentError):
    """Base class for errors from external APIs."""

    status_code = 502


class WeatherAPIError(ExternalServiceError):
    """Raised when a weather API call fails or returns invalid data."""

    status_code = 502


class NASAPOWERError(ExternalServiceError):
    """Raised when the NASA POWER API call fails."""

    status_code = 502


# ------------------------------------------------------------------ #
# Data
# ------------------------------------------------------------------ #


class DataValidationError(FarmingAgentError):
    """Raised when input data fails validation before processing."""

    status_code = 422


class MissingDataError(FarmingAgentError):
    """Raised when required data is absent and cannot be safely imputed."""

    status_code = 422


# ------------------------------------------------------------------ #
# ML / RL
# ------------------------------------------------------------------ #


class ModelNotFoundError(FarmingAgentError):
    """Raised when a requested ML or RL model artifact does not exist."""

    status_code = 404


class ModelInferenceError(FarmingAgentError):
    """Raised when ML or RL model inference fails."""

    status_code = 500


# ------------------------------------------------------------------ #
# Resource
# ------------------------------------------------------------------ #


class ResourceNotFoundError(FarmingAgentError):
    """Raised when a requested resource (farm, field, zone, …) does not exist."""

    status_code = 404


class ResourceConflictError(FarmingAgentError):
    """Raised when a resource cannot be created because it already exists."""

    status_code = 409


# ------------------------------------------------------------------ #
# Phase 4 — Data Acquisition
# ------------------------------------------------------------------ #


class NASAPOWERError(FarmingAgentError):
    """Raised when the NASA POWER API request fails or returns invalid data."""

    status_code = 502


class WeatherAPIError(FarmingAgentError):
    """Raised when the OpenWeatherMap API request fails or the key is invalid."""

    status_code = 502


class ET0CalculationError(FarmingAgentError):
    """Raised when FAO-56 Penman-Monteith ET0 cannot be computed (missing inputs)."""

    status_code = 422
