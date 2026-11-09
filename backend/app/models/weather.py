"""
WeatherRecord and ET0Record models.

WeatherRecord stores raw weather observations from NASA POWER or
OpenWeatherMap APIs. All values are validated before storage.

ET0Record stores the computed FAO-56 Penman-Monteith reference
evapotranspiration alongside the ML-predicted ET₀ from Phase 8.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.engine import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.zone import Zone


class WeatherRecord(Base, TimestampMixin):
    """
    Daily weather observation for a farm location.

    Data sourced from NASA POWER API (solar radiation, humidity, wind)
    or OpenWeatherMap (temperature, precipitation). The ``source`` field
    records provenance.

    All numeric fields use SI units as per FAO-56 conventions.

    Attributes
    ----------
    id : int
        Primary key.
    farm_id : int
        FK → farms.id — weather is fetched per farm centroid.
    observation_date : date
        The calendar date of the observation (UTC).
    source : str
        "NASA_POWER", "OpenWeatherMap", or "simulated".
    temperature_max_c : float | None
        Maximum daily air temperature in °C.
    temperature_min_c : float | None
        Minimum daily air temperature in °C.
    temperature_mean_c : float | None
        Mean daily air temperature in °C.
    humidity_max_pct : float | None
        Maximum relative humidity in %.
    humidity_min_pct : float | None
        Minimum relative humidity in %.
    humidity_mean_pct : float | None
        Mean relative humidity in %.
    wind_speed_m_s : float | None
        Wind speed at 2 m height in m/s (FAO-56 standard height).
    solar_radiation_mj_m2 : float | None
        Incoming solar radiation in MJ/m² per day.
    precipitation_mm : float | None
        Total daily precipitation in mm.
    pressure_kpa : float | None
        Atmospheric pressure in kPa.
    dew_point_c : float | None
        Dew point temperature in °C.
    sunshine_hours : float | None
        Actual sunshine duration in hours.
    raw_response : str | None
        JSON dump of the original API response for debugging.
    """

    __tablename__ = "weather_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="simulated")

    # Temperature (°C)
    temperature_max_c: Mapped[float | None] = mapped_column(Float)
    temperature_min_c: Mapped[float | None] = mapped_column(Float)
    temperature_mean_c: Mapped[float | None] = mapped_column(Float)

    # Humidity (%)
    humidity_max_pct: Mapped[float | None] = mapped_column(Float)
    humidity_min_pct: Mapped[float | None] = mapped_column(Float)
    humidity_mean_pct: Mapped[float | None] = mapped_column(Float)

    # Wind, radiation, precip
    wind_speed_m_s: Mapped[float | None] = mapped_column(Float)
    solar_radiation_mj_m2: Mapped[float | None] = mapped_column(Float)
    precipitation_mm: Mapped[float | None] = mapped_column(Float)
    pressure_kpa: Mapped[float | None] = mapped_column(Float)
    dew_point_c: Mapped[float | None] = mapped_column(Float)
    sunshine_hours: Mapped[float | None] = mapped_column(Float)

    raw_response: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return (
            f"<WeatherRecord id={self.id} farm_id={self.farm_id} "
            f"date={self.observation_date} source={self.source!r}>"
        )


class ET0Record(Base, TimestampMixin):
    """
    Reference evapotranspiration record for a zone.

    Stores both the FAO-56 Penman-Monteith computed ET₀ and the
    ML-predicted ET₀ (from the LSTM/ANN in Phase 8). The two values
    are kept separate so performance metrics can be computed.

    Also stores derived crop water need (ETc = Kc × ET₀).

    Attributes
    ----------
    id : int
        Primary key.
    zone_id : int
        FK → zones.id.
    farm_id : int
        FK → farms.id — used to join with WeatherRecord.
    record_date : date
        The date for which ET₀ was computed.
    et0_penman_monteith_mm : float | None
        FAO-56 Penman-Monteith ET₀ in mm/day. Computed analytically.
    et0_ml_predicted_mm : float | None
        ML model (LSTM/ANN) ET₀ prediction in mm/day. Set in Phase 8.
    kc_used : float | None
        Crop coefficient (Kc) used to compute ETc.
    etc_mm : float | None
        Crop evapotranspiration ETc = Kc × ET₀ in mm/day.
    effective_rainfall_mm : float | None
        Effective rainfall (fraction of precipitation usable by crops).
    net_irrigation_requirement_mm : float | None
        NIR = ETc − effective_rainfall (if positive, irrigation needed).
    computation_method : str
        "FAO56_PM" or "ML_LSTM" or "combined".
    notes : str | None
        Free-text notes.
    """

    __tablename__ = "et0_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    farm_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    et0_penman_monteith_mm: Mapped[float | None] = mapped_column(Float)
    et0_ml_predicted_mm: Mapped[float | None] = mapped_column(Float)
    kc_used: Mapped[float | None] = mapped_column(Float)
    etc_mm: Mapped[float | None] = mapped_column(Float)
    effective_rainfall_mm: Mapped[float | None] = mapped_column(Float)
    net_irrigation_requirement_mm: Mapped[float | None] = mapped_column(Float)
    computation_method: Mapped[str] = mapped_column(
        String(50), nullable=False, default="FAO56_PM"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    zone: Mapped["Zone"] = relationship("Zone", back_populates="et0_records")

    def __repr__(self) -> str:
        return (
            f"<ET0Record id={self.id} zone_id={self.zone_id} "
            f"date={self.record_date} ET0_PM={self.et0_penman_monteith_mm}mm>"
        )
