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


class AdminUserMembership(BaseModel):
    household_id: uuid.UUID
    household_name: str
    role: HouseholdRole


class AdminUserSummary(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    is_instance_admin: bool
    created_at: datetime
    # Empty means orphaned -- a real account with nowhere to log into (see
    # auth.py's login() rejecting any user with no memberships). The user-
    # management UI's "reset" action (POST .../memberships below) exists
    # specifically to fix this case without the broken self-service
    # register/accept-invite path Vikunja #101 found.
    memberships: list[AdminUserMembership]


class AdminAddMembershipRequest(BaseModel):
    household_id: uuid.UUID
    role: HouseholdRole = HouseholdRole.MEMBER
