import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.maintenance_schedule import IntervalType


class MaintenanceScheduleCreate(BaseModel):
    asset_id: uuid.UUID
    name: str
    interval_type: IntervalType
    interval_days: int | None = None
    interval_usage_amount: int | None = None
    usage_field: str | None = None
    anchor_date: date | None = None
    anchor_usage_value: int | None = None


class MaintenanceScheduleUpdate(BaseModel):
    name: str | None = None
    interval_days: int | None = None
    interval_usage_amount: int | None = None
    anchor_date: date | None = None
    anchor_usage_value: int | None = None
    active: bool | None = None
    dismissed_at: datetime | None = None


class MaintenanceScheduleResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    asset_id: uuid.UUID
    name: str
    interval_type: IntervalType
    interval_days: int | None
    interval_usage_amount: int | None
    usage_field: str | None
    anchor_date: date | None
    anchor_usage_value: int | None
    active: bool
    dismissed_at: datetime | None
    next_due_date: date | None
    next_due_usage: int | None
    is_overdue: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
