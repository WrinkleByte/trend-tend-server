import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.household import HouseholdRole


class AdminHouseholdMember(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    display_name: str
    role: HouseholdRole
    is_instance_admin: bool
    joined_at: datetime


class AdminHouseholdRecordCounts(BaseModel):
    assets: int
    fuel_logs: int
    trip_logs: int
    maintenance_records: int
    maintenance_schedules: int


class AdminHouseholdSummary(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    members: list[AdminHouseholdMember]
    record_counts: AdminHouseholdRecordCounts


class PromoteUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_instance_admin: bool
