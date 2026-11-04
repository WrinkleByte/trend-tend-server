# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid
from datetime import datetime

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}
