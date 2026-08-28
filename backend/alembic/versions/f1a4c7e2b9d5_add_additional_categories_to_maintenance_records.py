"""add additional_categories to maintenance_records

Comma-joined category keys beyond the record's single primary `category`,
for multi-category tagging of one service entry (Vikunja: "tag multiple
categories to a single service entry"). Additive only -- `category` stays
unchanged as the primary value every existing display site reads.

Revision ID: f1a4c7e2b9d5
Revises: b58f0d3e6a1c
Create Date: 2026-08-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a4c7e2b9d5'
down_revision: Union[str, None] = 'b58f0d3e6a1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('maintenance_records', sa.Column('additional_categories', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('maintenance_records', 'additional_categories')
