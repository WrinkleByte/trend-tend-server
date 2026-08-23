import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class MaintenanceRecordCreate(BaseModel):
    asset_id: uuid.UUID
    performed_at: date
    performed_by: str | None = None
    category: str
    custom_category: str | None = None
    description: str | None = None
    cost: Decimal | None = None
    currency: str = "USD"
    odometer_reading: int | None = None
    schedule_id: uuid.UUID | None = None
    oil_viscosity: str | None = None
    oil_formulation: str | None = None
    oil_meets_dexos: bool | None = None
    filter_part_number: str | None = None
    fluid_type: str | None = None


class MaintenanceRecordBulkCreate(BaseModel):
    # Deliberately raw dicts, not list[MaintenanceRecordCreate] -- see
    # FuelLogBulkCreate's doc comment for why (Pydantic validates a nested
    # model list atomically, which would 422 the whole batch on one bad row).
    items: list[dict]


class MaintenanceRecordBulkResult(BaseModel):
    index: int
    status: Literal["created", "error"]
    id: uuid.UUID | None = None
    error: str | None = None


class MaintenanceRecordUpdate(BaseModel):
    performed_at: date | None = None
    performed_by: str | None = None
    category: str | None = None
    custom_category: str | None = None
    description: str | None = None
    cost: Decimal | None = None
    currency: str | None = None
    odometer_reading: int | None = None
    oil_viscosity: str | None = None
    oil_formulation: str | None = None
    oil_meets_dexos: bool | None = None
    filter_part_number: str | None = None
    fluid_type: str | None = None


class MaintenanceRecordResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    asset_id: uuid.UUID
    performed_at: date
    performed_by: str | None
    category: str
    custom_category: str | None
    description: str | None
    cost: Decimal | None
    currency: str
    odometer_reading: int | None
    schedule_id: uuid.UUID | None
    oil_viscosity: str | None
    oil_formulation: str | None
    oil_meets_dexos: bool | None
    filter_part_number: str | None
    fluid_type: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
