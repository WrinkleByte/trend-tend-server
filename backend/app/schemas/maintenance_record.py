import uuid
from datetime import date, datetime
from decimal import Decimal

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


class MaintenanceRecordUpdate(BaseModel):
    performed_at: date | None = None
    performed_by: str | None = None
    category: str | None = None
    custom_category: str | None = None
    description: str | None = None
    cost: Decimal | None = None
    currency: str | None = None
    odometer_reading: int | None = None


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
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
