# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""add maintenance_schedules.dismissed_at for cross-device alert dismissal sync

Revision ID: a1c3d8f6b2e4
Revises: 7f5c78942e3e
Create Date: 2026-08-21 09:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c3d8f6b2e4'
down_revision: Union[str, None] = '7f5c78942e3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('maintenance_schedules', sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('maintenance_schedules', 'dismissed_at')
