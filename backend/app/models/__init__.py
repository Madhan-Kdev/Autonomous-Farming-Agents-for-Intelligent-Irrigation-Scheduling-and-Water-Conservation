"""
Models package — registers all SQLAlchemy ORM models.

Importing this package ensures all models are registered with the
``Base`` metadata so Alembic autogenerate can discover them.

Import order matters: models with no FK dependencies must be imported
before models that reference them.
"""

# 1. Base mixin (no table, no FKs)
from app.models.base import TimestampMixin  # noqa: F401

# 2. Top-level entities
from app.models.farm import Farm, Field  # noqa: F401

# 3. Zone (depends on Field)
from app.models.zone import SoilProfile, Zone  # noqa: F401

# 4. Crop (independent of zone/farm)
from app.models.crop import Crop, CropGrowthStage  # noqa: F401

# 5. Weather and ET0 (depends on Farm, Zone)
from app.models.weather import ET0Record, WeatherRecord  # noqa: F401

# 6. Irrigation (depends on Zone, Farm)
from app.models.irrigation import IrrigationRecord  # noqa: F401

# 7. Agent execution log (depends on Farm)
from app.models.agent_log import AgentExecutionLog  # noqa: F401

__all__ = [
    "TimestampMixin",
    "Farm",
    "Field",
    "Zone",
    "SoilProfile",
    "Crop",
    "CropGrowthStage",
    "WeatherRecord",
    "ET0Record",
    "IrrigationRecord",
    "AgentExecutionLog",
]
