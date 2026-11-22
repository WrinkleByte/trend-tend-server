# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only
"""add brand to maintenance records

Revision ID: a4f6c1d8b2e5
Revises: d7c2f4a1b8e3
Create Date: 2026-11-22

Card #823, found by the cross-repo contract test (tests/test_sync_contract.py).

The shipped mobile app records which brand a job actually used -- maintenanceRecord.brand,
added on 2026-11-21 and shipping in TestFlight 1.5.0 build 16 -- and sends it on every
record push. The backend never declared it and never had a column for it, so Pydantic
dropped it at parse time: the brand lived only on the phone that typed it, and a second
device that edited the same record would rewrite it without ever knowing it was there.

Its Service-Defaults cousins are already carried by d7c2f4a1b8e3; this is the per-record
half. Additive and nullable: no existing row changes, nothing to copy.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4f6c1d8b2e5"
down_revision: Union[str, None] = "d7c2f4a1b8e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("maintenance_records", sa.Column("brand", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("maintenance_records", "brand")
