"""
Generic base repository providing CRUD operations for all ORM models.

Every specialised repository inherits from ``BaseRepository[T]`` and
gets create/read/update/delete without writing boilerplate.
"""

from __future__ import annotations

from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.engine import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """
    Generic synchronous repository for a SQLAlchemy ORM model.

    Usage::

        class FarmRepository(BaseRepository[Farm]):
            def __init__(self, db: Session) -> None:
                super().__init__(Farm, db)

    Parameters
    ----------
    model_class:
        The SQLAlchemy ORM model class.
    db:
        An active SQLAlchemy ``Session``.
    """

    def __init__(self, model_class: Type[T], db: Session) -> None:
        self._model = model_class
        self._db = db

    # ------------------------------------------------------------------ #
    # Create
    # ------------------------------------------------------------------ #

    def create(self, **kwargs: Any) -> T:
        """Create and persist a new instance."""
        instance = self._model(**kwargs)
        self._db.add(instance)
        self._db.flush()  # Get the PK without committing the transaction.
        self._db.refresh(instance)
        return instance

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #

    def get_by_id(self, record_id: int) -> T | None:
        """Return a single record by primary key, or None."""
        return self._db.get(self._model, record_id)

    def get_all(self, limit: int = 100, offset: int = 0) -> Sequence[T]:
        """Return all records with optional pagination."""
        stmt = select(self._model).limit(limit).offset(offset)
        return self._db.execute(stmt).scalars().all()

    def count(self) -> int:
        """Return the total number of rows in the table."""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(self._model)
        return self._db.execute(stmt).scalar_one()

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #

    def update(self, record_id: int, **kwargs: Any) -> T | None:
        """Update fields on an existing record. Returns None if not found."""
        instance = self.get_by_id(record_id)
        if instance is None:
            return None
        for key, value in kwargs.items():
            setattr(instance, key, value)
        self._db.flush()
        self._db.refresh(instance)
        return instance

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #

    def delete(self, record_id: int) -> bool:
        """Delete a record by PK. Returns True if deleted, False if not found."""
        instance = self.get_by_id(record_id)
        if instance is None:
            return False
        self._db.delete(instance)
        self._db.flush()
        return True
