# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""add maintenance_categories table

A household's remembered custom service-type names -- see
app/models/maintenance_category.py's doc comment. Pure remembered-name
list, no foreign key relationship from maintenance_records.

Revision ID: e7c4b91a2f3d
Revises: d4a92b6f0c31
Create Date: 2026-08-24 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7c4b91a2f3d'
down_revision: Union[str, None] = 'd4a92b6f0c31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'maintenance_categories',
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('household_id', sa.UUID(), nullable=False),
        sa.Column('updated_by_device_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ),
        sa.ForeignKeyConstraint(['updated_by_device_id'], ['sync_devices.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_maintenance_categories_household_id'), 'maintenance_categories', ['household_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_maintenance_categories_household_id'), table_name='maintenance_categories')
    op.drop_table('maintenance_categories')
