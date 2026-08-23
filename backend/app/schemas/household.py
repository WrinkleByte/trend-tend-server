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


class HouseholdSettingsUpdate(BaseModel):
    """Household-owner-settable defaults for the mobile apps' device-global
    cosmetic/unit settings (see tendfida-mobile's AppSettings.swift /
    AndroidAppSettings.kt) -- an individual device can still locally
    override any of these. Values mirror the same CarDisplayTheme raw
    cases / UnitFormatter.unitSystem(key) "imperial"/"metric" keys used by
    the per-vehicle override fields on VehicleDetailsIn. Merged into (not
    replacing) Household.settings on update, so that JSONB column stays
    forward-compatible with unrelated future keys this schema doesn't know
    about yet."""

    car_display_theme: str | None = None
    stylized_plate_enabled: bool | None = None
    unit_system: str | None = None


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
