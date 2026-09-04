"""Alembic migration environment.

Wired to the application settings (COUNSELCONNECT_* environment variables)
and the shared SQLAlchemy metadata in app.db.base. The versions/ directory
is intentionally empty: the approved CounselConnect_Initial_Database_v4.sql
is the canonical baseline, and the first revision will be a baseline
migration generated from the approved models (do not fake history).
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make backend/ importable when alembic runs from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.db.base import Base, import_all_models  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the runtime database URL from application settings.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

# Register every module's models so autogenerate sees full metadata.
import_all_models()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a DBAPI connection (emit SQL to script)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "format"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live database connection."""
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
