# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.capabilities import API_VERSION, CAPABILITIES
from app.core.version import APP_VERSION

router = APIRouter(tags=["meta"])


class MetaResponse(BaseModel):
    server_version: str
    api_version: int
    capabilities: list[str]


@router.get("/meta", response_model=MetaResponse)
async def meta() -> MetaResponse:
    """What this server is and what it supports. No sign-in needed: it's the
    first thing a client asks, and it reveals nothing beyond the version that
    /health already shows. See app/core/capabilities.py for the rules."""
    return MetaResponse(server_version=APP_VERSION, api_version=API_VERSION, capabilities=list(CAPABILITIES))
