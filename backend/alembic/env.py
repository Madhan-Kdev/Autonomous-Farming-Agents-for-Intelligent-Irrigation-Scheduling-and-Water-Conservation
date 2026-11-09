"""
Alembic environment configuration.

Reads DATABASE_URL from the application settings (via pydantic-settings)
so there is a single source of truth for the connection string.

Supports both:
* ``alembic upgrade head``  — online mode (database must be reachable).
* ``alembic revision --autogenerate``  — generates migration scripts from
  the SQLAlchemy model metadata.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ------------------------------------------------------------------ #
# Make sure app/ is importable from the backend/ directory.
# ------------------------------------------------------------------ #
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set required env vars before importing app modules so pydantic-settings
# does not fail on systems where DATABASE_URL is not in the OS environment.
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

from app.core.config import get_settings
from app.database.engine import Base

# Import ALL models so Alembic autogenerate can discover them.
import app.models  # noqa: F401  — triggers model registration

# ------------------------------------------------------------------ #
# Alembic Config
# ------------------------------------------------------------------ #
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url with the value from our settings.
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Provide the metadata for autogenerate support.
target_metadata = Base.metadata


# ------------------------------------------------------------------ #
# Migration runners
# ------------------------------------------------------------------ #

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Emits SQL to stdout/file without connecting to a live database.
    Useful for generating migration SQL to review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates a real database connection and applies pending migrations.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
