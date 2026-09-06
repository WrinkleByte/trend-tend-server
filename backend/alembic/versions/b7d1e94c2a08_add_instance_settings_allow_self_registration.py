"""add instance_settings.allow_self_registration to let admins close signups

Revision ID: b7d1e94c2a08
Revises: e2b6f813a4c9
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d1e94c2a08'
down_revision: Union[str, None] = 'e2b6f813a4c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default='true' rather than just the model-level default: an
    # existing row is backfilled by the ALTER itself, so an instance that
    # upgrades mid-flight doesn't come up with signups silently closed.
    op.add_column(
        'instance_settings',
        sa.Column('allow_self_registration', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column('instance_settings', 'allow_self_registration')
