import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class FuelLogCreate(BaseModel):
    asset_id: uuid.UUID
    performed_at: date
    odometer_reading: int | None = None
    gallons: Decimal
    cost_per_gallon: Decimal | None = None
    total_cost: Decimal | None = None
    currency: str = "USD"
    is_fill_up: bool = True
    mpg: Decimal | None = None
    octane: int | None = None
    cetane: int | None = None
    gas_brand: str | None = None
    location: str | None = None
    notes: str | None = None
    additive: str | None = None


class FuelLogUpdate(BaseModel):
    performed_at: date | None = None
    odometer_reading: int | None = None
    gallons: Decimal | None = None
    cost_per_gallon: Decimal | None = None
    total_cost: Decimal | None = None
    currency: str | None = None
    is_fill_up: bool | None = None
    mpg: Decimal | None = None
    octane: int | None = None
    cetane: int | None = None
    gas_brand: str | None = None
    location: str | None = None
    notes: str | None = None
    additive: str | None = None


class FuelLogResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    asset_id: uuid.UUID
    performed_at: date
    odometer_reading: int | None
    gallons: Decimal
    cost_per_gallon: Decimal | None
    total_cost: Decimal | None
    currency: str
    is_fill_up: bool
    mpg: Decimal | None
    octane: int | None
    cetane: int | None
    gas_brand: str | None
    location: str | None
    notes: str | None
    additive: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
