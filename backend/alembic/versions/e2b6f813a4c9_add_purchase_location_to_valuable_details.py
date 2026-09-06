"""add purchase_location to valuable_details

Revision ID: e2b6f813a4c9
Revises: c1a7e3f92b48
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2b6f813a4c9'
down_revision: Union[str, None] = 'c1a7e3f92b48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('valuable_details', sa.Column('purchase_location', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('valuable_details', 'purchase_location')
