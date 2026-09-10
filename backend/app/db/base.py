"""DeclarativeBase with stable naming conventions for Alembic autogeneration.

Table/column/index names come from the approved v4.1 SQL
(CounselConnect_Initial_Database_v4.1.sql) — models must not rename them.
"""

from __future__ import annotations

import importlib

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "idx_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    # Models pass fully-qualified names (chk_<table>_<name>) in CheckConstraint
    # itself, so no additional prefix is rendered here. A convention key would
    # double the prefix (chk_<table>_chk_<table>_<name>) and make autogenerate
    # try to rename every CHECK in the deployed schema.
    "ck": "%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


_MODEL_MODULES = (
    "app.modules.accounts.models",
    "app.modules.appointments.models",
    "app.modules.audit.models",
    "app.modules.auth.models",
    "app.modules.content.models",
    "app.modules.enrollment_verification.models",
    "app.modules.messaging.models",
    "app.modules.sos.models",
    "app.modules.wellness_resources.models",
)


def import_all_models() -> None:
    """Idempotently import every module's models for metadata registration.

    Called by Alembic's env.py (and any code needing complete metadata).
    Imports exist for their side effect (Base.metadata registration), so
    importlib is used to avoid redefinition/rebinding linter warnings.
    """
    for module_name in _MODEL_MODULES:
        importlib.import_module(module_name)
