"""
Core package exports for the Autonomous Farming Agents backend.

Note: ``settings`` is a lazy proxy — the underlying Settings object is
constructed only on first attribute access, allowing test fixtures to
set environment variables before the object is created.
"""

from app.core.config import Settings, _reset_settings, get_settings, settings
from app.core.exceptions import (
    AgentConfigurationError,
    AgentError,
    AgentStateError,
    AgentTimeoutError,
    ConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    DataValidationError,
    ExternalServiceError,
    FarmingAgentError,
    MissingDataError,
    ModelInferenceError,
    ModelNotFoundError,
    NASAPOWERError,
    OrchestratorError,
    ResourceConflictError,
    ResourceNotFoundError,
    WeatherAPIError,
    WorkflowError,
)
from app.core.logging_config import get_logger, setup_logging

__all__ = [
    # Config
    "Settings",
    "get_settings",
    "settings",
    "_reset_settings",
    # Logging
    "setup_logging",
    "get_logger",
    # Exceptions
    "FarmingAgentError",
    "ConfigurationError",
    "DatabaseError",
    "DatabaseConnectionError",
    "AgentError",
    "AgentTimeoutError",
    "AgentStateError",
    "AgentConfigurationError",
    "OrchestratorError",
    "WorkflowError",
    "ExternalServiceError",
    "WeatherAPIError",
    "NASAPOWERError",
    "DataValidationError",
    "MissingDataError",
    "ModelNotFoundError",
    "ModelInferenceError",
    "ResourceNotFoundError",
    "ResourceConflictError",
]
