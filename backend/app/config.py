from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The literal shipped as jwt_secret's default. Named so the startup guard
# below can recognise it: this value is in a public repo, so any instance
# still running it has a forgeable auth system — anyone can mint a token
# for any user in any household. Must never be the effective secret
# outside an explicitly dev-mode instance.
INSECURE_DEFAULT_JWT_SECRET = "dev-secret-change-me"

# HS256 keys shorter than the hash output add no security beyond their own
# length; PyJWT warns about this at runtime (InsecureKeyLengthWarning).
MIN_JWT_SECRET_BYTES = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://wrinklebyte:wrinklebyte@localhost:5432/wrinklebyte"

    # Opt-in escape hatch for the startup guard in _reject_insecure_defaults
    # below. Set DEV_MODE=true for local dev / CI / the docker-compose stack;
    # never in a real deployment. Deliberately defaults to False so that
    # forgetting it fails loudly rather than silently running insecurely —
    # the safe state is the default, and the unsafe one takes an explicit act.
    dev_mode: bool = False

    jwt_secret: str = INSECURE_DEFAULT_JWT_SECRET
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

    @model_validator(mode="after")
    def _reject_insecure_defaults(self) -> "Settings":
        """Refuse to start an instance whose auth could be trivially forged.

        This project is open-source and self-hosted by design, so the default
        jwt_secret below isn't merely weak — it's public knowledge. An
        instance running it lets anyone mint an access token for any
        household, with no exploit required. That's a silent failure with no
        symptom until someone notices, which is exactly the kind of mistake a
        self-hoster shouldn't be able to make by omission, so it's fatal at
        boot rather than a logged warning.
        """
        if self.dev_mode:
            return self

        problems = []
        if self.jwt_secret == INSECURE_DEFAULT_JWT_SECRET:
            problems.append(
                "JWT_SECRET is still the built-in default, which is published in this "
                "project's source — anyone could forge tokens for any account."
            )
        elif len(self.jwt_secret.encode("utf-8")) < MIN_JWT_SECRET_BYTES:
            problems.append(
                f"JWT_SECRET is shorter than {MIN_JWT_SECRET_BYTES} bytes, which weakens HS256 signing."
            )

        if problems:
            raise ValueError(
                "Refusing to start with an insecure configuration:\n"
                + "\n".join(f"  - {p}" for p in problems)
                + "\n\nGenerate one with:  python -c \"import secrets; print(secrets.token_urlsafe(48))\"\n"
                "then set JWT_SECRET in your environment or .env file.\n"
                "For local development only, set DEV_MODE=true to bypass this check."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
