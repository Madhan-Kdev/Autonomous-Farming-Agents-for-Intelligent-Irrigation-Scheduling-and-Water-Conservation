"""
Common FastAPI dependencies used across multiple endpoints.
"""

from typing import Generator

from sqlalchemy.orm import Session

from app.database.engine import get_db

# Re-export for convenience so endpoints can import from app.api.dependencies.
__all__ = ["get_db"]
