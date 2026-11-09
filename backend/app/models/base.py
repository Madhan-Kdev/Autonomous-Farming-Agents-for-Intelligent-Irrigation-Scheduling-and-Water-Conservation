"""
SQLAlchemy Base model with shared mixins.

All ORM models inherit from ``Base`` (defined in ``database.engine``).
The ``TimestampMixin`` adds ``created_at`` / ``updated_at`` to every table
that needs audit columns.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.engine import Base


class TimestampMixin:
    """
    Adds ``created_at`` and ``updated_at`` audit columns.

    * ``created_at`` — set once at INSERT time by the database server.
    * ``updated_at`` — updated automatically on every UPDATE by the server.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="UTC timestamp when the row was first inserted.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="UTC timestamp of the most recent UPDATE.",
    )
