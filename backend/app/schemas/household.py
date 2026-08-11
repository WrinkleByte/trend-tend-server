import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.household import HouseholdRole, InviteStatus


class HouseholdResponse(BaseModel):
    id: uuid.UUID
    name: str
    owner_user_id: uuid.UUID
    settings: dict
    created_at: datetime
    # The caller's own role in this household — lets clients conditionally
    # show owner-only actions (invite/revoke/remove-member) without a
    # separate "who am I" lookup.
    my_role: HouseholdRole

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


class HouseholdMemberResponse(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    display_name: str
    role: HouseholdRole
    joined_at: datetime


class InviteCreate(BaseModel):
    invited_email: EmailStr
    role: HouseholdRole = HouseholdRole.MEMBER


class InviteResponse(BaseModel):
    id: uuid.UUID
    invited_email: str
    role: HouseholdRole
    status: InviteStatus
    token: str
    created_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


class InvitePreviewResponse(BaseModel):
    """What an unauthenticated visitor sees at a `/join?token=...` link
    before deciding to register or accept — deliberately excludes the
    household's id/owner/settings, which the invite token doesn't need to
    reveal."""

    household_name: str
    invited_email: str
    role: HouseholdRole
    status: InviteStatus
    expires_at: datetime


class AcceptInviteRequest(BaseModel):
    token: str
