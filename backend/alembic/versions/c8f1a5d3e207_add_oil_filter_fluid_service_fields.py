"""add oil/filter/fluid structured service fields to maintenance_records and vehicle_details

Revision ID: c8f1a5d3e207
Revises: a3f7c2e9d146
Create Date: 2026-08-23 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8f1a5d3e207'
down_revision: Union[str, None] = 'a3f7c2e9d146'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('maintenance_records', sa.Column('oil_viscosity', sa.String(length=50), nullable=True))
    op.add_column('maintenance_records', sa.Column('oil_formulation', sa.String(length=30), nullable=True))
    op.add_column('maintenance_records', sa.Column('oil_meets_dexos', sa.Boolean(), nullable=True))
    op.add_column('maintenance_records', sa.Column('filter_part_number', sa.String(length=100), nullable=True))
    op.add_column('maintenance_records', sa.Column('fluid_type', sa.String(length=100), nullable=True))

    op.add_column('vehicle_details', sa.Column('default_oil_viscosity', sa.String(length=50), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_oil_formulation', sa.String(length=30), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_oil_meets_dexos', sa.Boolean(), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_oil_filter_part_number', sa.String(length=100), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_air_filter_part_number', sa.String(length=100), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_transmission_fluid_type', sa.String(length=100), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_coolant_type', sa.String(length=100), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_differential_front_fluid_type', sa.String(length=100), nullable=True))
    op.add_column('vehicle_details', sa.Column('default_differential_rear_fluid_type', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('vehicle_details', 'default_differential_rear_fluid_type')
    op.drop_column('vehicle_details', 'default_differential_front_fluid_type')
    op.drop_column('vehicle_details', 'default_coolant_type')
    op.drop_column('vehicle_details', 'default_transmission_fluid_type')
    op.drop_column('vehicle_details', 'default_air_filter_part_number')
    op.drop_column('vehicle_details', 'default_oil_filter_part_number')
    op.drop_column('vehicle_details', 'default_oil_meets_dexos')
    op.drop_column('vehicle_details', 'default_oil_formulation')
    op.drop_column('vehicle_details', 'default_oil_viscosity')

    op.drop_column('maintenance_records', 'fluid_type')
    op.drop_column('maintenance_records', 'filter_part_number')
    op.drop_column('maintenance_records', 'oil_meets_dexos')
    op.drop_column('maintenance_records', 'oil_formulation')
    op.drop_column('maintenance_records', 'oil_viscosity')
