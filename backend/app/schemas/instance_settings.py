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

    model_config = {"from_attributes": True}
