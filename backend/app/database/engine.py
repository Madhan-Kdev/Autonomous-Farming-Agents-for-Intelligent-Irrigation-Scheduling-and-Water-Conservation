"""
SQLAlchemy engine, session factory, and declarative base.

All database interaction in the application goes through the session
obtained from ``get_db``.  The engine is configured once at module import
time using the ``settings`` singleton.
"""

from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.core.exceptions import DatabaseConnectionError

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Engine
# ------------------------------------------------------------------ #

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO_SQL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,   # Detect stale connections before use.
    pool_recycle=1800,    # Recycle connections after 30 min.
)

# ------------------------------------------------------------------ #
# Session Factory
# ------------------------------------------------------------------ #

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# ------------------------------------------------------------------ #
# Declarative Base
# ------------------------------------------------------------------ #


class Base(DeclarativeBase):
    """
    Shared SQLAlchemy declarative base for all ORM models.

    All SQLAlchemy models must inherit from this class so that
    ``Base.metadata.create_all(engine)`` discovers them automatically.
    """


# ------------------------------------------------------------------ #
# Dependency
# ------------------------------------------------------------------ #


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.

    Ensures the session is always closed, even if an exception occurs.

    Usage::

        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------------------------------------------ #
# Health Check
# ------------------------------------------------------------------ #


def check_database_connection() -> bool:
    """
    Execute ``SELECT 1`` to verify database connectivity.

    Returns
    -------
    bool
        ``True`` if the database is reachable, ``False`` otherwise.

    Raises
    ------
    DatabaseConnectionError
        If the connection check itself raises an unexpected exception.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.debug("Database connectivity check: OK")
        return True
    except Exception as exc:
        logger.error("Database connectivity check failed: %s", exc)
        return False
