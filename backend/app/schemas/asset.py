# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

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


class EquipmentDetailsIn(BaseModel):
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    warranty_expiration: date | None = None
    car_display_theme: str | None = None
    unit_system_override: str | None = None


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
    # Optional owner within the household — powers the client-side "only show
    # my stuff" filter. Not a permission: see Asset.owner_user_id. Verified to
    # be a member of this household by the endpoint before it's stored.
    owner_user_id: uuid.UUID | None = None
    vehicle_details: VehicleDetailsIn | None = None
    equipment_details: EquipmentDetailsIn | None = None
    property_details: PropertyDetailsIn | None = None
    valuable_details: ValuableDetailsIn | None = None


class AssetUpdate(BaseModel):
    name: str | None = None
    notes: str | None = None
    status: AssetStatus | None = None
    purchase_date: date | None = None
    purchase_cost: Decimal | None = None
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


class AssetResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    asset_type: AssetType
    name: str
    notes: str | None
    status: AssetStatus
    purchase_date: date | None
    purchase_cost: Decimal | None
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

    model_config = {"from_attributes": True}
