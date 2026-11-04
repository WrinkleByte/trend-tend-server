# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""make fuel_log.gallons nullable so an entry can be saved with only a date

Revision ID: d2c7a91f4b36
Revises: c3f8b2d41e07
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2c7a91f4b36'
down_revision: Union[str, None] = 'c3f8b2d41e07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL means "volume not recorded", which is deliberately distinct from a
    # stored 0: consumers (fuel economy, cost-per-gallon) skip NULL rather
    # than averaging it in as a genuine zero-gallon fill-up.
    op.alter_column(
        'fuel_logs',
        'gallons',
        existing_type=sa.Numeric(8, 3),
        nullable=True,
    )


def downgrade() -> None:
    # Rows added since the upgrade may legitimately hold NULL, and there is no
    # correct value to invent for them -- 0 would be a lie that silently skews
    # every MPG average. Fill them in before downgrading.
    op.execute("DELETE FROM fuel_logs WHERE gallons IS NULL")
    op.alter_column(
        'fuel_logs',
        'gallons',
        existing_type=sa.Numeric(8, 3),
        nullable=False,
    )
