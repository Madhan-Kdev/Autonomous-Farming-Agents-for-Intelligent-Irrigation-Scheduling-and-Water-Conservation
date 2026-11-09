"""
IrrigationRecord model.

Records every irrigation event (recommended or actually applied) for
every zone. This is the primary dataset used by the HistoricalAgent
and the reinforcement learning environment.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.engine import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.zone import Zone


class IrrigationRecord(Base, TimestampMixin):
    """
    A single irrigation event for a zone.

    Captures both the agent's recommendation and the actual outcome,
    enabling the system to compute scheduling effectiveness metrics.

    Attributes
    ----------
    id : int
        Primary key.
    zone_id : int
        FK → zones.id.
    farm_id : int
        FK → farms.id.
    scheduled_at : datetime
        UTC timestamp when the irrigation was scheduled/recommended.
    decision : str
        Agent decision: "REQUIRED", "POSTPONED", "NOT_REQUIRED",
        "INSUFFICIENT_DATA".
    recommended_volume_mm : float | None
        Recommended irrigation depth in mm.
    recommended_duration_min : float | None
        Recommended duration in minutes (derived from mm + flow rate).
    actual_volume_mm : float | None
        Actually applied irrigation depth in mm (from simulation).
    actual_duration_min : float | None
        Actual duration applied in minutes.
    was_applied : bool
        Whether irrigation was actually applied (True) or skipped (False).
    soil_moisture_before_pct : float | None
        Soil moisture % before irrigation.
    soil_moisture_after_pct : float | None
        Soil moisture % after irrigation.
    et0_on_day_mm : float | None
        ET₀ on the day of this decision in mm.
    etc_on_day_mm : float | None
        ETc on the day of this decision in mm.
    precipitation_on_day_mm : float | None
        Precipitation on the day of this decision in mm.
    decision_confidence : float | None
        Agent confidence score [0, 1].
    irrigation_method : str | None
        "drip", "sprinkler", "flood", etc.
    reasoning_summary : str | None
        Short text summary of the agent reasoning (NOT LLM-generated numbers).
    notes : str | None
        Free-text notes.
    """

    __tablename__ = "irrigation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    farm_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    recommended_volume_mm: Mapped[float | None] = mapped_column(Float)
    recommended_duration_min: Mapped[float | None] = mapped_column(Float)
    actual_volume_mm: Mapped[float | None] = mapped_column(Float)
    actual_duration_min: Mapped[float | None] = mapped_column(Float)
    was_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    soil_moisture_before_pct: Mapped[float | None] = mapped_column(Float)
    soil_moisture_after_pct: Mapped[float | None] = mapped_column(Float)
    et0_on_day_mm: Mapped[float | None] = mapped_column(Float)
    etc_on_day_mm: Mapped[float | None] = mapped_column(Float)
    precipitation_on_day_mm: Mapped[float | None] = mapped_column(Float)

    decision_confidence: Mapped[float | None] = mapped_column(Float)
    irrigation_method: Mapped[str | None] = mapped_column(String(50))
    reasoning_summary: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    zone: Mapped["Zone"] = relationship("Zone", back_populates="irrigation_records")

    def __repr__(self) -> str:
        return (
            f"<IrrigationRecord id={self.id} zone_id={self.zone_id} "
            f"decision={self.decision!r} applied={self.was_applied}>"
        )
