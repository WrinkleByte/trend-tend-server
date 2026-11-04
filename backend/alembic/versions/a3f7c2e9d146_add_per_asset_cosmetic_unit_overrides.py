# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""add per-asset cosmetic/unit-system override columns to vehicle_details and equipment_details

Revision ID: a3f7c2e9d146
Revises: 4591a286a5fb
Create Date: 2026-08-22 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c2e9d146'
down_revision: Union[str, None] = '4591a286a5fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vehicle_details', sa.Column('car_display_theme', sa.String(length=30), nullable=True))
    op.add_column('vehicle_details', sa.Column('stylized_plate_enabled', sa.Boolean(), nullable=True))
    op.add_column('vehicle_details', sa.Column('unit_system_override', sa.String(length=10), nullable=True))
    op.add_column('equipment_details', sa.Column('car_display_theme', sa.String(length=30), nullable=True))
    op.add_column('equipment_details', sa.Column('unit_system_override', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('equipment_details', 'unit_system_override')
    op.drop_column('equipment_details', 'car_display_theme')
    op.drop_column('vehicle_details', 'unit_system_override')
    op.drop_column('vehicle_details', 'stylized_plate_enabled')
    op.drop_column('vehicle_details', 'car_display_theme')
