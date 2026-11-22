# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""move remembered service specs into one asset-level service_defaults table

Revision ID: d7c2f4a1b8e3
Revises: b7e3f9a2c415
Create Date: 2026-11-21 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7c2f4a1b8e3'
down_revision: Union[str, None] = 'b7e3f9a2c415'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every column that today lives on vehicle_details as a remembered service
# spec, in the order it was added to that table. Names are carried across
# unchanged -- `vehicle_details.default_oil_filter_part_number` becomes
# `service_defaults.default_oil_filter_part_number` -- because the wire field
# names clients send are these names. Renaming them here would mean every
# client had to be rewritten in the same release as this migration; keeping
# them is what lets an old app and a new app write the same value through
# different payloads (see app/schemas/service_defaults.py).
_RELOCATED = [
    ("default_oil_viscosity", sa.String(length=50)),
    ("default_oil_formulation", sa.String(length=30)),
    ("default_oil_meets_dexos", sa.Boolean()),
    ("default_oil_filter_part_number", sa.String(length=100)),
    ("default_air_filter_part_number", sa.String(length=100)),
    ("default_transmission_fluid_type", sa.String(length=100)),
    ("default_coolant_type", sa.String(length=100)),
    ("default_differential_front_fluid_type", sa.String(length=100)),
    ("default_differential_rear_fluid_type", sa.String(length=100)),
    ("default_oil_capacity", sa.String(length=50)),
    ("default_transmission_filter_part_number", sa.String(length=100)),
    ("default_transmission_fluid_capacity", sa.String(length=50)),
    ("default_differential_front_capacity", sa.String(length=50)),
    ("default_differential_rear_capacity", sa.String(length=100)),
]

# New fields, all nullable, that only the mobile app's own screens set. They
# arrive with no data, exactly as the mobile migration (its 22.sqm) creates
# them, so a household that never used them looks identical before and after.
_ADDED = [
    # Brands: mobile shipped these in its 21.sqm with no server-side
    # counterpart at all -- every saved brand a phone stored since then has
    # been dropped by the sync layer on the way to the server. This is where
    # they land.
    ("default_motor_oil_brand", sa.String(length=100)),
    ("default_oil_filter_brand", sa.String(length=100)),
    ("default_air_filter_brand", sa.String(length=100)),
    # Equipment (generators, mowers, tractors): EQUIPMENT_CATEGORIES already
    # offers fuel_filter and hydraulic_fluid service records, so the specs
    # those records need have a demand today and had nowhere to be remembered.
    ("default_fuel_filter_part_number", sa.String(length=100)),
    ("default_fuel_filter_brand", sa.String(length=100)),
    ("default_hydraulic_fluid_type", sa.String(length=100)),
    ("default_hydraulic_fluid_capacity", sa.String(length=50)),
    # Property / home_system: PROPERTY_CATEGORIES already offers
    # hvac_filter_change and water_filter_change.
    ("default_hvac_filter_size", sa.String(length=100)),
    ("default_hvac_filter_brand", sa.String(length=100)),
    ("default_water_filter_cartridge", sa.String(length=100)),
    ("default_water_filter_brand", sa.String(length=100)),
]


def upgrade() -> None:
    op.create_table(
        "service_defaults",
        sa.Column("asset_id", sa.UUID(), nullable=False),
        *[sa.Column(name, type_, nullable=True) for name, type_ in _RELOCATED + _ADDED],
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("asset_id"),
    )

    # Carry the existing rows across, then -- and this ordering is the whole
    # point -- only then drop the old columns. Copy first means that at no
    # point between this migration and the next deploy is a saved spec absent
    # from the database: a crash, a failed deploy, or a downgrade halfway
    # through all leave the values in one of the two tables, never in neither.
    #
    # Both sides spell their column lists out. `INSERT ... SELECT *` would
    # silently misalign every row the moment the two tables drift by one
    # column, and it would corrupt them quietly rather than failing.
    relocated = ", ".join(name for name, _ in _RELOCATED)
    op.execute(
        f"""
        INSERT INTO service_defaults (asset_id, {relocated})
        SELECT asset_id, {relocated}
        FROM vehicle_details
        """
    )

    for name, type_ in _RELOCATED:
        op.drop_column("vehicle_details", name)


def downgrade() -> None:
    for name, type_ in _RELOCATED:
        op.add_column("vehicle_details", sa.Column(name, type_, nullable=True))

    relocated = ", ".join(name for name, _ in _RELOCATED)
    op.execute(
        f"""
        UPDATE vehicle_details
        SET ({relocated}) = (
            SELECT sd.{relocated.replace(", ", ", sd.")}
            FROM service_defaults sd
            WHERE sd.asset_id = vehicle_details.asset_id
        )
        WHERE EXISTS (SELECT 1 FROM service_defaults sd WHERE sd.asset_id = vehicle_details.asset_id)
        """
    )

    op.drop_table("service_defaults")
