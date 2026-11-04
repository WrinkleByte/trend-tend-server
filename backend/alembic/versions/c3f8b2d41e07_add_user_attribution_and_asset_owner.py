# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""add updated_by_user_id to every synced entity, and assets.owner_user_id

Revision ID: c3f8b2d41e07
Revises: b7d1e94c2a08
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f8b2d41e07'
down_revision: Union[str, None] = 'b7d1e94c2a08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Every table carrying SyncedEntityMixin — kept as an explicit list rather
# than reflected from the metadata so this migration keeps doing exactly what
# it did the day it ran, even after a future entity joins the mixin.
SYNCED_TABLES = (
    'assets',
    'maintenance_records',
    'maintenance_schedules',
    'fuel_logs',
    'trip_logs',
    'maintenance_categories',
    'attachments',
)


def upgrade() -> None:
    for table in SYNCED_TABLES:
        # Nullable with no backfill: rows that predate this column genuinely
        # have no answer for "who changed this", and inventing one (e.g. the
        # household owner) would be a fabricated audit trail.
        op.add_column(table, sa.Column('updated_by_user_id', sa.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f'fk_{table}_updated_by_user_id_users',
            table,
            'users',
            ['updated_by_user_id'],
            ['id'],
        )

    op.add_column('assets', sa.Column('owner_user_id', sa.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_assets_owner_user_id_users', 'assets', 'users', ['owner_user_id'], ['id']
    )
    # Indexed because the "only show my stuff" filter is a per-request WHERE
    # on this column for every asset list a filtering client loads.
    op.create_index('ix_assets_owner_user_id', 'assets', ['owner_user_id'])


def downgrade() -> None:
    op.drop_index('ix_assets_owner_user_id', table_name='assets')
    op.drop_constraint('fk_assets_owner_user_id_users', 'assets', type_='foreignkey')
    op.drop_column('assets', 'owner_user_id')

    for table in SYNCED_TABLES:
        op.drop_constraint(f'fk_{table}_updated_by_user_id_users', table, type_='foreignkey')
        op.drop_column(table, 'updated_by_user_id')
