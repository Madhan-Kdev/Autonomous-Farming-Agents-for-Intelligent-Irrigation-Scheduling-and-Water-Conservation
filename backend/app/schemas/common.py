"""
Common API response schemas used across all endpoints.

All endpoint responses should wrap their payload in one of these models
to ensure consistent structure that the frontend can rely on.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ------------------------------------------------------------------ #
# Base Response
# ------------------------------------------------------------------ #


class APIResponse(BaseModel, Generic[T]):
    """
    Generic success response envelope.

    All successful API responses use this model so that the frontend
    always receives a consistent ``{ success, data, message, timestamp }``
    structure.

    Example::

        APIResponse[HealthStatus](
            success=True,
            data=health_status,
            message="System is healthy",
        )
    """

    success: bool = Field(default=True, description="True for successful responses.")
    data: T | None = Field(default=None, description="Response payload.")
    message: str = Field(default="", description="Human-readable status message.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the response.",
    )


class ErrorResponse(BaseModel):
    """
    Standard error response envelope returned by exception handlers.

    Registered in ``main.py`` for all ``FarmingAgentError`` subclasses.
    """

    success: bool = Field(default=False)
    error: str = Field(description="Exception class name.")
    message: str = Field(description="Human-readable error description.")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured diagnostic context.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Response wrapper for paginated list endpoints."""

    success: bool = True
    data: list[T] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total number of records in the dataset.")
    page: int = Field(ge=1, description="Current page number (1-indexed).")
    page_size: int = Field(ge=1, description="Number of records per page.")
    total_pages: int = Field(ge=0, description="Total number of pages.")
    message: str = ""
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
