"""add latitude/longitude to fuel_logs

Vikunja #100 (mobile): the fill-up's real-world coordinates, captured
automatically at save time on mobile -- no map picker, no station search.
Independent of the existing `location` free-text column.

Revision ID: d848a7618446
Revises: a8e2f6c40d17
Create Date: 2026-08-31 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd848a7618446'
down_revision: Union[str, None] = 'a8e2f6c40d17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fuel_logs', sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('fuel_logs', sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True))


def downgrade() -> None:
    op.drop_column('fuel_logs', 'longitude')
    op.drop_column('fuel_logs', 'latitude')
