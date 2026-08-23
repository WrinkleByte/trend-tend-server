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


class AssetCreate(BaseModel):
    asset_type: AssetType
    name: str
    notes: str | None = None
    purchase_date: date | None = None
    purchase_cost: Decimal | None = None
    vehicle_details: VehicleDetailsIn | None = None
    equipment_details: EquipmentDetailsIn | None = None
    property_details: PropertyDetailsIn | None = None


class AssetUpdate(BaseModel):
    name: str | None = None
    notes: str | None = None
    status: AssetStatus | None = None
    purchase_date: date | None = None
    purchase_cost: Decimal | None = None
    vehicle_details: VehicleDetailsIn | None = None
    equipment_details: EquipmentDetailsIn | None = None
    property_details: PropertyDetailsIn | None = None


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
    version: int
    created_at: datetime
    updated_at: datetime
    vehicle_details: VehicleDetailsIn | None = None
    equipment_details: EquipmentDetailsIn | None = None
    property_details: PropertyDetailsIn | None = None

    model_config = {"from_attributes": True}
