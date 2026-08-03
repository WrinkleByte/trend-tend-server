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


class EquipmentDetailsIn(BaseModel):
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    warranty_expiration: date | None = None


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
    version: int
    created_at: datetime
    updated_at: datetime
    vehicle_details: VehicleDetailsIn | None = None
    equipment_details: EquipmentDetailsIn | None = None
    property_details: PropertyDetailsIn | None = None

    model_config = {"from_attributes": True}
