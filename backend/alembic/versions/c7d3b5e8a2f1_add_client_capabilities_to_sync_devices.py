# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only
"""add client-declared capabilities to sync_devices

Revision ID: c7d3b5e8a2f1
Revises: a4f6c1d8b2e5
Create Date: 2026-11-22

Card #828, second half of the handshake. The server already says what it can store
(server_capabilities on every pull, unsupported_fields on every accepted push). This is the
other direction: what the client told the server it can do, kept with the device.

Three nullable columns. Nullable matters: a device registered before this carries NULL, and
NULL must stay distinguishable from an empty list. "Never declared anything" means the
server treats that device as a legacy superset client and keeps serving it the old shapes;
"declared an empty list" would mean something else entirely, and a migration that backfilled
either one would silently reclassify every paired phone in the household.

Deliberately its own revision rather than folded into d7c2f4a1b8e3, which was already
validated against a copy of production data.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c7d3b5e8a2f1"
down_revision: Union[str, None] = "a4f6c1d8b2e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sync_devices", sa.Column("client_version", sa.String(length=50), nullable=True))
    op.add_column("sync_devices", sa.Column("capabilities", JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "sync_devices",
        sa.Column("capabilities_reported_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sync_devices", "capabilities_reported_at")
    op.drop_column("sync_devices", "capabilities")
    op.drop_column("sync_devices", "client_version")
