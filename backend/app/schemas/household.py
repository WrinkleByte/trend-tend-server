import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.household import HouseholdRole


class HouseholdResponse(BaseModel):
    id: uuid.UUID
    name: str
    owner_user_id: uuid.UUID
    settings: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class HouseholdCreate(BaseModel):
    name: str


class MembershipResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    user_id: uuid.UUID
    role: HouseholdRole
    joined_at: datetime

    model_config = {"from_attributes": True}
