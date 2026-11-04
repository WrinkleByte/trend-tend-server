# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_instance_admin
from app.core.instance_settings import get_or_create_instance_settings
from app.db.session import get_db
from app.schemas.instance_settings import (
    InstanceSettingsResponse,
    InstanceSettingsUpdate,
)

router = APIRouter(prefix="/instance-settings", tags=["instance-settings"])


def _to_response(settings) -> InstanceSettingsResponse:
    return InstanceSettingsResponse(
        smtp_enabled=settings.smtp_enabled,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_use_tls=settings.smtp_use_tls,
        smtp_from_address=settings.smtp_from_address,
        smtp_password_set=bool(settings.smtp_password),
        public_api_url=settings.public_api_url,
        allow_self_registration=settings.allow_self_registration,
    )


@router.get("", response_model=InstanceSettingsResponse)
async def get_instance_settings(
    principal: Principal = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> InstanceSettingsResponse:
    settings = await get_or_create_instance_settings(db)
    return _to_response(settings)


@router.put("", response_model=InstanceSettingsResponse)
async def update_instance_settings(
    payload: InstanceSettingsUpdate,
    principal: Principal = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> InstanceSettingsResponse:
    settings = await get_or_create_instance_settings(db)

    for field in (
        "smtp_enabled",
        "smtp_host",
        "smtp_port",
        "smtp_username",
        "smtp_use_tls",
        "smtp_from_address",
        "public_api_url",
        "allow_self_registration",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(settings, field, value)

    # smtp_password is the one field where None genuinely means "leave
    # unchanged" (the response never echoes it back for the client to
    # round-trip) — an empty string is the only way to explicitly clear it.
    if payload.smtp_password is not None:
        settings.smtp_password = payload.smtp_password or None

    await db.commit()
    await db.refresh(settings)
    return _to_response(settings)
