"""add instance_settings.public_api_url for correct mobile pairing QR codes

Revision ID: 4591a286a5fb
Revises: 95d3e5f4643e
Create Date: 2026-08-22 21:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4591a286a5fb'
down_revision: Union[str, None] = '95d3e5f4643e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('instance_settings', sa.Column('public_api_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('instance_settings', 'public_api_url')
