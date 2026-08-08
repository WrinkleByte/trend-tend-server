from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://tendfida:tendfida@localhost:5432/tendfida"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = 15
    jwt_refresh_token_ttl_days: int = 30

    storage_backend: Literal["local_disk", "s3"] = "local_disk"
    storage_local_root: str = "./data/attachments"
    storage_s3_bucket: str = ""
    storage_s3_endpoint_url: str = ""
    storage_s3_access_key: str = ""
    storage_s3_secret_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
