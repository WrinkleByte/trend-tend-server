# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

from pydantic import BaseModel


class InstanceSettingsUpdate(BaseModel):
    smtp_enabled: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    # None = leave unchanged; "" clears it. Distinguishing the two is why
    # this can't just default to None-means-both — see
    # api/v1/instance_settings.py's update handler.
    smtp_password: str | None = None
    smtp_use_tls: bool | None = None
    smtp_from_address: str | None = None
    # None = leave unchanged, same as the other plain string fields above
    # (smtp_host etc.) -- "" is a valid value here too and is treated as
    # "not configured" by the frontend (falls back to
    # window.location.origin for the pairing QR code), not specially
    # distinguished from None the way smtp_password is.
    public_api_url: str | None = None
    # None = leave unchanged, same as every other field here.
    allow_self_registration: bool | None = None


class InstanceSettingsResponse(BaseModel):
    smtp_enabled: bool
    smtp_host: str | None
    smtp_port: int | None
    smtp_username: str | None
    # Deliberately omits smtp_password entirely rather than returning it
    # (even masked) — this is the one place in the schema that's writable
    # but never read back.
    smtp_use_tls: bool
    smtp_from_address: str | None
    smtp_password_set: bool
    public_api_url: str | None
    allow_self_registration: bool

    model_config = {"from_attributes": True}
