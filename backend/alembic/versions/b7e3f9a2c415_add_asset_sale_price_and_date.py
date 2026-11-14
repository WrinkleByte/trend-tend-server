# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""add assets.sale_price and assets.sale_date, recorded when an asset is retired

Revision ID: b7e3f9a2c415
Revises: d2c7a91f4b36
Create Date: 2026-11-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e3f9a2c415'
down_revision: Union[str, None] = 'd2c7a91f4b36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both nullable with no default: every existing asset simply has no sale
    # recorded, which is the truth.
    op.add_column('assets', sa.Column('sale_price', sa.Numeric(10, 2), nullable=True))
    op.add_column('assets', sa.Column('sale_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('assets', 'sale_date')
    op.drop_column('assets', 'sale_price')
