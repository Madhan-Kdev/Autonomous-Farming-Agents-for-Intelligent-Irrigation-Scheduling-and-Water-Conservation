"""
Zone and SoilProfile models.

A Zone is an independently irrigatable sub-unit of a Field.
Each Zone can have its own SoilProfile (sensor readings + lab data).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.engine import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.crop import CropGrowthStage
    from app.models.farm import Field
    from app.models.irrigation import IrrigationRecord
    from app.models.weather import ET0Record


class Zone(Base, TimestampMixin):
    """
    An independently irrigatable zone within a field.

    The zone is the atomic irrigation unit — every irrigation decision
    is made at zone level by the ZoneIrrigationAgent.

    Attributes
    ----------
    id : int
        Primary key.
    field_id : int
        FK → fields.id.
    name : str
        Zone identifier (e.g. "Zone-1", "Drip Block A").
    zone_number : int
        Sequential zone index within the field (1-based).
    area_ha : float
        Zone area in hectares.
    irrigation_method : str | None
        "drip", "sprinkler", "flood", "furrow", etc.
    max_irrigation_mm : float | None
        Maximum single-event irrigation depth in mm.
    min_irrigation_mm : float | None
        Minimum threshold irrigation depth in mm.
    is_active : bool
        Whether this zone is currently managed by the system.
    crop_name : str | None
        Currently planted crop in this zone.
    notes : str | None
        Free-text notes.
    """

    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    zone_number: Mapped[int] = mapped_column(Integer, nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    irrigation_method: Mapped[str | None] = mapped_column(String(50))
    max_irrigation_mm: Mapped[float | None] = mapped_column(Float)
    min_irrigation_mm: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    crop_name: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    field: Mapped["Field"] = relationship("Field", back_populates="zones")
    soil_profiles: Mapped[list["SoilProfile"]] = relationship(
        "SoilProfile", back_populates="zone", cascade="all, delete-orphan"
    )
    irrigation_records: Mapped[list["IrrigationRecord"]] = relationship(
        "IrrigationRecord", back_populates="zone", cascade="all, delete-orphan"
    )
    et0_records: Mapped[list["ET0Record"]] = relationship(
        "ET0Record", back_populates="zone", cascade="all, delete-orphan"
    )
    growth_stages: Mapped[list["CropGrowthStage"]] = relationship(
        "CropGrowthStage", back_populates="zone", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Zone id={self.id} name={self.name!r} field_id={self.field_id}>"
        )


class SoilProfile(Base, TimestampMixin):
    """
    Soil moisture and physical property readings for a zone.

    All numerical values come from validated sensor simulation models
    (never from LLM outputs). The ``data_source`` field always records
    where values originated.

    Attributes
    ----------
    id : int
        Primary key.
    zone_id : int
        FK → zones.id.
    data_source : str
        Always "simulated" in Phase 3 (hardware sensors in later phases).
    volumetric_moisture_pct : float | None
        Volumetric water content as a percentage (0–100).
    field_capacity_pct : float | None
        Field capacity (upper limit) volumetric water content %.
    wilting_point_pct : float | None
        Permanent wilting point volumetric water content %.
    bulk_density_g_cm3 : float | None
        Soil bulk density in g/cm³.
    ph : float | None
        Soil pH (0–14).
    organic_matter_pct : float | None
        Soil organic matter content %.
    sand_pct : float | None
        Sand fraction % (sand + silt + clay = 100).
    silt_pct : float | None
        Silt fraction %.
    clay_pct : float | None
        Clay fraction %.
    electrical_conductivity_ds_m : float | None
        Electrical conductivity in dS/m (salinity indicator).
    depth_cm : float | None
        Measurement depth in cm.
    temperature_c : float | None
        Soil temperature at measurement depth in °C.
    notes : str | None
        Free-text notes.
    """

    __tablename__ = "soil_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="simulated"
    )
    volumetric_moisture_pct: Mapped[float | None] = mapped_column(Float)
    field_capacity_pct: Mapped[float | None] = mapped_column(Float)
    wilting_point_pct: Mapped[float | None] = mapped_column(Float)
    bulk_density_g_cm3: Mapped[float | None] = mapped_column(Float)
    ph: Mapped[float | None] = mapped_column(Float)
    organic_matter_pct: Mapped[float | None] = mapped_column(Float)
    sand_pct: Mapped[float | None] = mapped_column(Float)
    silt_pct: Mapped[float | None] = mapped_column(Float)
    clay_pct: Mapped[float | None] = mapped_column(Float)
    electrical_conductivity_ds_m: Mapped[float | None] = mapped_column(Float)
    depth_cm: Mapped[float | None] = mapped_column(Float)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    zone: Mapped["Zone"] = relationship("Zone", back_populates="soil_profiles")

    def __repr__(self) -> str:
        return (
            f"<SoilProfile id={self.id} zone_id={self.zone_id} "
            f"moisture={self.volumetric_moisture_pct}%>"
        )
