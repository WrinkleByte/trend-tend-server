"""add capacity fields and transmission filter part number to maintenance_records and vehicle_details

Revision ID: d4a92b6f0c31
Revises: c8f1a5d3e207
Create Date: 2026-08-23 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a92b6f0c31'
down_revision: Union[str, None] = 'c8f1a5d3e207'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('maintenance_records', sa.Column('capacity', sa.String(length=50), nullable=True))

    op.add_column('vehicle_details', sa.Column('default_oil_capacity', sa.String(length=50), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_transmission_filter_part_number', sa.String(length=100), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_transmission_fluid_capacity', sa.String(length=50), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_differential_front_capacity', sa.String(length=50), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_differential_rear_capacity', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('vehicle_details', 'default_differential_rear_capacity')
    op.drop_column('vehicle_details', 'default_differential_front_capacity')
    op.drop_column('vehicle_details', 'default_transmission_fluid_capacity')
    op.drop_column('vehicle_details', 'default_transmission_filter_part_number')
    op.drop_column('vehicle_details', 'default_oil_capacity')

    op.drop_column('maintenance_records', 'capacity')
