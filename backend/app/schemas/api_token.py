# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ApiTokenCreate(BaseModel):
    name: str
    expires_at: datetime | None = None


class ApiTokenCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    # The raw token, shown once at creation time only — only its hash is
    # ever stored, so this is the only response that ever includes it.
    token: str
    scopes: dict
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class ApiTokenResponse(BaseModel):
    id: uuid.UUID
    name: str
    scopes: dict
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    # Set when someone else (a household owner or instance admin) made this
    # key for its user; None when the user made it themselves.
    created_by_user_id: uuid.UUID | None = None
    created_by_name: str | None = None

    model_config = {"from_attributes": True}


class MemberApiTokenCreate(BaseModel):
    """A pairing key an owner/admin makes for another member, e.g. "Kate's iPhone"."""

    name: str = Field(min_length=1, max_length=200)
    expires_at: datetime | None = None


class AdminApiTokenCreate(MemberApiTokenCreate):
    # A key belongs to one household; the user must be a member of it.
    household_id: uuid.UUID


class AdminApiTokenResponse(ApiTokenResponse):
    # The admin view spans households, so say which one each key is for.
    household_id: uuid.UUID
