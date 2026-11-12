# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""add api_tokens.created_by_user_id, for keys an owner/admin issues to someone else

Revision ID: a4e8c2f61d93
Revises: d2c7a91f4b36
Create Date: 2026-11-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a4e8c2f61d93'
down_revision: Union[str, None] = 'd2c7a91f4b36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: NULL means the key's own user made it, which is true of every
    # key that exists today.
    op.add_column(
        'api_tokens',
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_api_tokens_created_by_user_id_users',
        'api_tokens',
        'users',
        ['created_by_user_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_api_tokens_created_by_user_id_users', 'api_tokens', type_='foreignkey')
    op.drop_column('api_tokens', 'created_by_user_id')
