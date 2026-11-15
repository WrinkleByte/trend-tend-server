# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid

from pydantic import BaseModel, Field, field_validator


class MeResponse(BaseModel):
    user_id: uuid.UUID
    # "" for an app-only member added without an address (see
    # app/core/api_token_issuing.py's public_email).
    email: str
    display_name: str
    has_login: bool


class MeUpdate(BaseModel):
    """Fields a user may change about themselves. Each is optional so more
    can be added later without breaking older clients; one left out is left
    as it is."""

    display_name: str | None = Field(default=None, max_length=200)

    @field_validator("display_name")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be blank")
        return value
