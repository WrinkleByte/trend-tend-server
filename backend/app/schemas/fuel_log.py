import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

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
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    notes: str | None = None
    additive: str | None = None


class FuelLogBulkCreate(BaseModel):
    # Deliberately raw dicts, not list[FuelLogCreate] -- Pydantic validates a
    # nested model list atomically, so one malformed row (bad date format, a
    # non-numeric decimal) would 422 the whole request before the endpoint
    # ever runs, silently dropping every valid row too. Each item is
    # validated individually inside the endpoint instead, so a bad row
    # becomes one "error" result rather than killing the batch.
    items: list[dict]


class FuelLogBulkResult(BaseModel):
    index: int
    status: Literal["created", "error"]
    id: uuid.UUID | None = None
    error: str | None = None


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
    latitude: Decimal | None = None
    longitude: Decimal | None = None
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
    latitude: Decimal | None
    longitude: Decimal | None
    notes: str | None
    additive: str | None
    # Who in the household last changed this row. Server-set from the
    # authenticated principal, never client-supplied — see
    # SyncedEntityMixin.updated_by_user_id.
    updated_by_user_id: uuid.UUID | None = None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
