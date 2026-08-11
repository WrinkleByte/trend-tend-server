import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TripLogCreate(BaseModel):
    asset_id: uuid.UUID
    performed_at: datetime
    purpose: str
    custom_purpose: str | None = None
    start_odometer: Decimal | None = None
    end_odometer: Decimal
    distance: Decimal
    notes: str | None = None


class TripLogUpdate(BaseModel):
    performed_at: datetime | None = None
    purpose: str | None = None
    custom_purpose: str | None = None
    start_odometer: Decimal | None = None
    end_odometer: Decimal | None = None
    distance: Decimal | None = None
    notes: str | None = None


class TripLogResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    asset_id: uuid.UUID
    performed_at: datetime
    purpose: str
    custom_purpose: str | None
    start_odometer: Decimal | None
    end_odometer: Decimal
    distance: Decimal
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
