# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""add plate_style to vehicle_details

Vikunja #103: which stylized plate design to draw when
stylized_plate_enabled resolves true. Plain per-vehicle attribute,
additive only.

Revision ID: a8e2f6c40d17
Revises: f1a4c7e2b9d5
Create Date: 2026-08-29 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8e2f6c40d17'
down_revision: Union[str, None] = 'f1a4c7e2b9d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vehicle_details', sa.Column('plate_style', sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column('vehicle_details', 'plate_style')
