# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.attachment import StorageBackendType


class AttachmentResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    storage_backend: StorageBackendType
    sha256: str
    thumbnail_storage_key: str | None
    captured_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    url: str

    model_config = {"from_attributes": True}
