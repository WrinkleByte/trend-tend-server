from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://wrinklebyte:wrinklebyte@localhost:5432/wrinklebyte"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = 15
    jwt_refresh_token_ttl_days: int = 30

    # Base URL of the web app, used to build links in outgoing email (just
    # password-reset today). No trailing slash. Must be set to the real
    # public URL in production — the localhost default only makes sense for
    # local dev, since it's baked into an email that could be opened from
    # any device.
    frontend_url: str = "http://localhost:5173"

    storage_backend: Literal["local_disk", "s3"] = "local_disk"
    storage_local_root: str = "./data/attachments"
    storage_s3_bucket: str = ""
    storage_s3_endpoint_url: str = ""
    storage_s3_access_key: str = ""
    storage_s3_secret_key: str = ""

    # One-time seed for the DB-backed instance_settings singleton (see
    # core/instance_settings.py) — only applied the first time that row is
    # created. After that, the admin instance-settings UI/API is the source
    # of truth and these env vars are never read again, unless
    # smtp_force_env is set.
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int | None = None
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_address: str = ""
    # Re-applies the smtp_* env vars above on every read instead of just at
    # creation, overwriting anything set via the admin instance-settings
    # UI — for deployments that want .env to be the sole SMTP source of
    # truth rather than a one-time default.
    smtp_force_env: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
