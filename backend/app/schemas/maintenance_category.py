import uuid
from datetime import datetime

from pydantic import BaseModel


class MaintenanceCategoryCreate(BaseModel):
    name: str


class MaintenanceCategoryUpdate(BaseModel):
    name: str | None = None


class MaintenanceCategoryResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
