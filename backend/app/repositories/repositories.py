"""
Specialised repositories for every ORM model.

Each repository extends ``BaseRepository`` with model-specific query methods.
All queries use SQLAlchemy 2.x ``select()`` style.
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_log import AgentExecutionLog
from app.models.crop import Crop, CropGrowthStage
from app.models.farm import Farm, Field
from app.models.irrigation import IrrigationRecord
from app.models.weather import ET0Record, WeatherRecord
from app.models.zone import SoilProfile, Zone
from app.repositories.base_repository import BaseRepository


# ================================================================== #
# Farm Repository
# ================================================================== #

class FarmRepository(BaseRepository[Farm]):
    def __init__(self, db: Session) -> None:
        super().__init__(Farm, db)

    def get_by_name(self, name: str) -> Farm | None:
        stmt = select(Farm).where(Farm.name == name)
        return self._db.execute(stmt).scalar_one_or_none()

    def get_all_active(self) -> Sequence[Farm]:
        return self.get_all(limit=1000)


# ================================================================== #
# Field Repository
# ================================================================== #

class FieldRepository(BaseRepository[Field]):
    def __init__(self, db: Session) -> None:
        super().__init__(Field, db)

    def get_by_farm(self, farm_id: int) -> Sequence[Field]:
        stmt = select(Field).where(Field.farm_id == farm_id)
        return self._db.execute(stmt).scalars().all()


# ================================================================== #
# Zone Repository
# ================================================================== #

class ZoneRepository(BaseRepository[Zone]):
    def __init__(self, db: Session) -> None:
        super().__init__(Zone, db)

    def get_by_field(self, field_id: int) -> Sequence[Zone]:
        stmt = select(Zone).where(Zone.field_id == field_id).order_by(Zone.zone_number)
        return self._db.execute(stmt).scalars().all()

    def get_active_zones(self, field_id: int) -> Sequence[Zone]:
        stmt = (
            select(Zone)
            .where(Zone.field_id == field_id, Zone.is_active == True)  # noqa: E712
            .order_by(Zone.zone_number)
        )
        return self._db.execute(stmt).scalars().all()


# ================================================================== #
# SoilProfile Repository
# ================================================================== #

class SoilProfileRepository(BaseRepository[SoilProfile]):
    def __init__(self, db: Session) -> None:
        super().__init__(SoilProfile, db)

    def get_latest_for_zone(self, zone_id: int) -> SoilProfile | None:
        stmt = (
            select(SoilProfile)
            .where(SoilProfile.zone_id == zone_id)
            .order_by(SoilProfile.created_at.desc())
            .limit(1)
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def get_all_for_zone(self, zone_id: int) -> Sequence[SoilProfile]:
        stmt = (
            select(SoilProfile)
            .where(SoilProfile.zone_id == zone_id)
            .order_by(SoilProfile.created_at.desc())
        )
        return self._db.execute(stmt).scalars().all()


# ================================================================== #
# Crop Repository
# ================================================================== #

class CropRepository(BaseRepository[Crop]):
    def __init__(self, db: Session) -> None:
        super().__init__(Crop, db)

    def get_by_name(self, name: str) -> Crop | None:
        stmt = select(Crop).where(Crop.name == name)
        return self._db.execute(stmt).scalar_one_or_none()

    def get_all_crops(self) -> Sequence[Crop]:
        stmt = select(Crop).order_by(Crop.name)
        return self._db.execute(stmt).scalars().all()


# ================================================================== #
# CropGrowthStage Repository
# ================================================================== #

class CropGrowthStageRepository(BaseRepository[CropGrowthStage]):
    def __init__(self, db: Session) -> None:
        super().__init__(CropGrowthStage, db)

    def get_current_for_zone(self, zone_id: int) -> CropGrowthStage | None:
        stmt = (
            select(CropGrowthStage)
            .where(CropGrowthStage.zone_id == zone_id)
            .order_by(CropGrowthStage.created_at.desc())
            .limit(1)
        )
        return self._db.execute(stmt).scalar_one_or_none()


# ================================================================== #
# WeatherRecord Repository
# ================================================================== #

class WeatherRecordRepository(BaseRepository[WeatherRecord]):
    def __init__(self, db: Session) -> None:
        super().__init__(WeatherRecord, db)

    def get_for_date(self, farm_id: int, obs_date: date) -> WeatherRecord | None:
        stmt = select(WeatherRecord).where(
            WeatherRecord.farm_id == farm_id,
            WeatherRecord.observation_date == obs_date,
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def get_recent(self, farm_id: int, days: int = 30) -> Sequence[WeatherRecord]:
        stmt = (
            select(WeatherRecord)
            .where(WeatherRecord.farm_id == farm_id)
            .order_by(WeatherRecord.observation_date.desc())
            .limit(days)
        )
        return self._db.execute(stmt).scalars().all()


# ================================================================== #
# ET0Record Repository
# ================================================================== #

class ET0RecordRepository(BaseRepository[ET0Record]):
    def __init__(self, db: Session) -> None:
        super().__init__(ET0Record, db)

    def get_for_date(self, zone_id: int, record_date: date) -> ET0Record | None:
        stmt = select(ET0Record).where(
            ET0Record.zone_id == zone_id,
            ET0Record.record_date == record_date,
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def get_recent(self, zone_id: int, days: int = 14) -> Sequence[ET0Record]:
        stmt = (
            select(ET0Record)
            .where(ET0Record.zone_id == zone_id)
            .order_by(ET0Record.record_date.desc())
            .limit(days)
        )
        return self._db.execute(stmt).scalars().all()


# ================================================================== #
# IrrigationRecord Repository
# ================================================================== #

class IrrigationRecordRepository(BaseRepository[IrrigationRecord]):
    def __init__(self, db: Session) -> None:
        super().__init__(IrrigationRecord, db)

    def get_recent_for_zone(
        self, zone_id: int, limit: int = 30
    ) -> Sequence[IrrigationRecord]:
        stmt = (
            select(IrrigationRecord)
            .where(IrrigationRecord.zone_id == zone_id)
            .order_by(IrrigationRecord.scheduled_at.desc())
            .limit(limit)
        )
        return self._db.execute(stmt).scalars().all()

    def get_applied_volume_mm(self, zone_id: int, since_date: date) -> float:
        """Total water applied to a zone since a given date in mm."""
        from sqlalchemy import func
        stmt = select(func.coalesce(func.sum(IrrigationRecord.actual_volume_mm), 0.0)).where(
            IrrigationRecord.zone_id == zone_id,
            IrrigationRecord.was_applied == True,  # noqa: E712
            IrrigationRecord.scheduled_at >= since_date,
        )
        return float(self._db.execute(stmt).scalar_one())


# ================================================================== #
# AgentExecutionLog Repository
# ================================================================== #

class AgentExecutionLogRepository(BaseRepository[AgentExecutionLog]):
    def __init__(self, db: Session) -> None:
        super().__init__(AgentExecutionLog, db)

    def get_by_run_id(self, run_id: str) -> Sequence[AgentExecutionLog]:
        stmt = (
            select(AgentExecutionLog)
            .where(AgentExecutionLog.run_id == run_id)
            .order_by(AgentExecutionLog.started_at)
        )
        return self._db.execute(stmt).scalars().all()

    def get_recent_failures(self, limit: int = 20) -> Sequence[AgentExecutionLog]:
        stmt = (
            select(AgentExecutionLog)
            .where(AgentExecutionLog.status == "FAILED")
            .order_by(AgentExecutionLog.started_at.desc())
            .limit(limit)
        )
        return self._db.execute(stmt).scalars().all()

