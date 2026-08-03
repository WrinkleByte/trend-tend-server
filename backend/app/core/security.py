import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import get_settings

settings = get_settings()
_hasher = PasswordHasher()

API_TOKEN_PREFIX = "mnt_live_"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(*, user_id: uuid.UUID, household_id: uuid.UUID, device_id: uuid.UUID | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "household_id": str(household_id),
        "device_id": str(device_id) if device_id else None,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(*, user_id: uuid.UUID, household_id: uuid.UUID, device_id: uuid.UUID | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "household_id": str(household_id),
        "device_id": str(device_id) if device_id else None,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_token_ttl_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError (or a subclass) on any invalid/expired token —
    callers should let it propagate into a 401, not swallow it silently."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def generate_api_token() -> tuple[str, str]:
    """Returns (raw_token_shown_once, token_hash_to_store)."""
    raw = API_TOKEN_PREFIX + secrets.token_urlsafe(32)
    return raw, hash_api_token(raw)


def hash_api_token(raw_token: str) -> str:
    # API tokens are high-entropy random strings (not low-entropy user
    # passwords), so a fast, deterministic hash is appropriate here — unlike
    # passwords, there's no need for argon2's deliberate slowness, and a
    # deterministic hash lets us look the token up by hash in one indexed query.
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def is_api_token(token: str) -> bool:
    return token.startswith(API_TOKEN_PREFIX)
