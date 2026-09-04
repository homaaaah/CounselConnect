"""baseline v4.1 schema

Revision ID: 8f0f8c585641
Revises: 
Create Date: 2026-09-04 06:33:31.223763

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8f0f8c585641'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
