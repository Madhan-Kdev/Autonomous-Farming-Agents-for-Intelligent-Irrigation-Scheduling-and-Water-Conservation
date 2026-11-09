"""
Farm and Field models.

Hierarchy: Farm → Field → Zone

A Farm is the top-level organisational unit owned by a farmer.
A Field is a physical area within a farm with known GPS boundaries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.engine import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.zone import Zone


class Farm(Base, TimestampMixin):
    """
    Represents a single farm managed by the system.

    Attributes
    ----------
    id : int
        Primary key.
    name : str
        Human-readable farm name (e.g. "Green Valley Farm").
    owner_name : str | None
        Name of the farm owner.
    location_description : str | None
        Free-text location (e.g. "Village Ramnagar, District Pune").
    latitude : float
        WGS-84 latitude of the farm centroid. Required for NASA POWER.
    longitude : float
        WGS-84 longitude of the farm centroid. Required for NASA POWER.
    altitude_m : float | None
        Elevation in metres above sea level. Used in ET₀ calculation.
    total_area_ha : float | None
        Total farm area in hectares.
    notes : str | None
        Free-text notes.
    """

    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    owner_name: Mapped[str | None] = mapped_column(String(200))
    location_description: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude_m: Mapped[float | None] = mapped_column(Float)
    total_area_ha: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    fields: Mapped[list["Field"]] = relationship(
        "Field", back_populates="farm", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Farm id={self.id} name={self.name!r}>"


class Field(Base, TimestampMixin):
    """
    A physical field (plot) within a farm.

    Fields are subdivided into irrigation Zones.

    Attributes
    ----------
    id : int
        Primary key.
    farm_id : int
        FK → farms.id.
    name : str
        Field identifier (e.g. "North Plot", "Field-3").
    area_ha : float
        Field area in hectares.
    soil_type : str | None
        Dominant soil texture class (e.g. "Sandy Loam", "Clay").
    latitude : float | None
        Field centroid latitude (defaults to farm latitude if not set).
    longitude : float | None
        Field centroid longitude.
    notes : str | None
        Free-text notes.
    """

    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    soil_type: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    farm: Mapped["Farm"] = relationship("Farm", back_populates="fields")
    zones: Mapped[list["Zone"]] = relationship(
        "Zone", back_populates="field", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Field id={self.id} name={self.name!r} farm_id={self.farm_id}>"
