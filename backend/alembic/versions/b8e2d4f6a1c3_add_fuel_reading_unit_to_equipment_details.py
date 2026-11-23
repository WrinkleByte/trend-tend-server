# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only
"""add fuel_reading_unit to equipment_details

Revision ID: b8e2d4f6a1c3
Revises: c7d3b5e8a2f1
Create Date: 2026-11-23

What a piece of equipment's fill-ups record: "hours" (its hour meter) or "odometer" (a
distance, for an ATV or a side-by-side). Nullable, no backfill: NULL means the default,
hours, which is what every existing piece of equipment already records. The reading itself
stays in fuel_logs.odometer_reading either way.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8e2d4f6a1c3"
down_revision: Union[str, None] = "c7d3b5e8a2f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("equipment_details", sa.Column("fuel_reading_unit", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("equipment_details", "fuel_reading_unit")
