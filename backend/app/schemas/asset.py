# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.asset import AssetStatus, AssetType


class VehicleDetailsIn(BaseModel):
    vin: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    license_plate: str | None = None
    current_mileage: int | None = None
    mileage_unit: str = "mi"
    fuel_type: str | None = None
    # Accepted and echoed here even though a brand was never a vehicle_details column: this
    # is the shape the shipped mobile build sends them in, and AssetResponse below reuses
    # this schema, so declaring them is also what lets the outbound mirror appear instead of
    # being dropped on the way out. Stored in service_defaults -- see VEHICLE_SIDE_NEW_FIELDS
    # in app/schemas/service_defaults.py.
    default_motor_oil_brand: str | None = None
    default_oil_filter_brand: str | None = None
    default_air_filter_brand: str | None = None
    car_display_theme: str | None = None
    stylized_plate_enabled: bool | None = None
    unit_system_override: str | None = None
    plate_style: str | None = None
    default_oil_viscosity: str | None = None
    default_oil_formulation: str | None = None
    default_oil_meets_dexos: bool | None = None
    default_oil_filter_part_number: str | None = None
    default_air_filter_part_number: str | None = None
    default_transmission_fluid_type: str | None = None
    default_coolant_type: str | None = None
    default_differential_front_fluid_type: str | None = None
    default_differential_rear_fluid_type: str | None = None
    default_oil_capacity: str | None = None
    default_transmission_filter_part_number: str | None = None
    default_transmission_fluid_capacity: str | None = None
    default_differential_front_capacity: str | None = None
    default_differential_rear_capacity: str | None = None


class ServiceDefaultsIn(BaseModel):
    """Remembered service specs, one row per asset, for every serviced asset type.

    The same field names VehicleDetailsIn has always carried for these, which is
    the point: an app that still sends them under `vehicle_details` and an app
    that sends them here are writing the identical value. See
    app/schemas/service_defaults.py for both halves of that compatibility path and
    why neither half is optional.

    Which subset a client shows depends on the asset type -- vehicle, equipment,
    property each get their own screen -- but the wire shape is one schema, and
    `valuable` assets get no row at all.
    """

    default_oil_viscosity: str | None = None
    default_oil_formulation: str | None = None
    default_oil_meets_dexos: bool | None = None
    default_oil_capacity: str | None = None
    default_motor_oil_brand: str | None = None
    default_oil_filter_part_number: str | None = None
    default_oil_filter_brand: str | None = None
    default_air_filter_part_number: str | None = None
    default_air_filter_brand: str | None = None
    default_fuel_filter_part_number: str | None = None
    default_fuel_filter_brand: str | None = None
    default_hydraulic_fluid_type: str | None = None
    default_hydraulic_fluid_capacity: str | None = None
    default_hvac_filter_size: str | None = None
    default_hvac_filter_brand: str | None = None
    default_water_filter_cartridge: str | None = None
    default_water_filter_brand: str | None = None
    default_transmission_fluid_type: str | None = None
    default_transmission_filter_part_number: str | None = None
    default_transmission_fluid_capacity: str | None = None
    default_coolant_type: str | None = None
    default_differential_front_fluid_type: str | None = None
    default_differential_front_capacity: str | None = None
    default_differential_rear_fluid_type: str | None = None
    default_differential_rear_capacity: str | None = None


# "hours" or "odometer" today. A plain short string rather than a Literal: a newer app
# with a third choice must not have its whole asset push rejected by an older server.
# Clients read anything but "odometer" as hours.
FuelReadingUnit = Annotated[str, Field(max_length=10)]


class EquipmentDetailsIn(BaseModel):
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    warranty_expiration: date | None = None
    car_display_theme: str | None = None
    unit_system_override: str | None = None
    # "hours" or "odometer"; None means hours. See EquipmentDetails.fuel_reading_unit.
    fuel_reading_unit: FuelReadingUnit | None = None


class PropertyDetailsIn(BaseModel):
    address: str | None = None
    parent_asset_id: uuid.UUID | None = None
    install_date: date | None = None


class ValuableDetailsIn(BaseModel):
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    warranty_expiration: date | None = None
    purchase_location: str | None = None
    linked_property_asset_id: uuid.UUID | None = None


class AssetCreate(BaseModel):
    asset_type: AssetType
    name: str
    notes: str | None = None
    purchase_date: date | None = None
    purchase_cost: Decimal | None = None
    sale_price: Decimal | None = Field(default=None, ge=0)
    sale_date: date | None = None
    # Optional owner within the household — powers the client-side "only show
    # my stuff" filter. Not a permission: see Asset.owner_user_id. Verified to
    # be a member of this household by the endpoint before it's stored.
    owner_user_id: uuid.UUID | None = None
    vehicle_details: VehicleDetailsIn | None = None
    equipment_details: EquipmentDetailsIn | None = None
    property_details: PropertyDetailsIn | None = None
    valuable_details: ValuableDetailsIn | None = None
    service_defaults: ServiceDefaultsIn | None = None


class AssetUpdate(BaseModel):
    name: str | None = None
    notes: str | None = None
    status: AssetStatus | None = None
    purchase_date: date | None = None
    purchase_cost: Decimal | None = None
    # Unlike the fields around them, these two can be cleared: sending
    # an explicit null clears, leaving the key out leaves it unchanged
    # (update_asset checks model_fields_set). Un-retiring an asset, or
    # correcting a sale entered by mistake, needs that.
    sale_price: Decimal | None = Field(default=None, ge=0)
    sale_date: date | None = None
    # None means "leave unchanged" here, same as every other field on this
    # partial-update schema — so there is deliberately no way to *clear* an
    # owner through this field alone. AssetUpdate has no other nullable-to-
    # null case today; if unassigning becomes a real need it wants an
    # explicit sentinel rather than overloading None.
    owner_user_id: uuid.UUID | None = None
    vehicle_details: VehicleDetailsIn | None = None
    equipment_details: EquipmentDetailsIn | None = None
    property_details: PropertyDetailsIn | None = None
    valuable_details: ValuableDetailsIn | None = None
    service_defaults: ServiceDefaultsIn | None = None


class AssetResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    asset_type: AssetType
    name: str
    notes: str | None
    status: AssetStatus
    purchase_date: date | None
    purchase_cost: Decimal | None
    sale_price: Decimal | None = None
    sale_date: date | None = None
    # Set via POST /attachments?asset_id=..., cleared via
    # DELETE /assets/{id}/photo -- not settable directly through
    # AssetCreate/AssetUpdate, same reasoning as record_id on the
    # attachment-upload endpoint: the relationship is driven by the upload
    # itself, not a raw id field a client could point anywhere.
    photo_attachment_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None
    # Who in the household last changed this row (server-set, never client-
    # supplied — see SyncedEntityMixin.updated_by_user_id). Null for rows
    # predating the column and for imported rows.
    updated_by_user_id: uuid.UUID | None = None
    version: int
    created_at: datetime
    updated_at: datetime
    vehicle_details: VehicleDetailsIn | None = None
    equipment_details: EquipmentDetailsIn | None = None
    property_details: PropertyDetailsIn | None = None
    valuable_details: ValuableDetailsIn | None = None
    service_defaults: ServiceDefaultsIn | None = None

    model_config = {"from_attributes": True}
