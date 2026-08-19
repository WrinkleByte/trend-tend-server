import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
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
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "household_id": str(household_id),
        "device_id": str(device_id) if device_id else None,
        "type": "access",
        "iat": now,
        # Sub-second issue time. `iat` is whole-second by spec, which leaves
        # a one-second window where a token cannot be ordered against a
        # password reset -- see reject_if_token_predates_invalidation.
        "iat_us": now.timestamp(),
        "exp": now + timedelta(minutes=settings.jwt_access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    *,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    device_id: uuid.UUID | None = None,
    jti: uuid.UUID | None = None,
    family_id: uuid.UUID | None = None,
) -> str:
    """Mint a refresh token.

    `jti` and `family_id` back rotation with reuse detection (see
    models/refresh_token.py). They're optional so this stays usable in
    tests and any caller that doesn't need rotation, but the auth
    endpoints always pass them -- a token minted without a jti cannot be
    rotated or revoked, only left to expire.
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "household_id": str(household_id),
        "device_id": str(device_id) if device_id else None,
        "type": "refresh",
        "iat": now,
        "iat_us": now.timestamp(),
        "exp": now + timedelta(days=settings.jwt_refresh_token_ttl_days),
    }
    if jti is not None:
        payload["jti"] = str(jti)
    if family_id is not None:
        payload["family_id"] = str(family_id)
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


def generate_invite_token() -> str:
    # Unlike API tokens, an invite token is a single-purpose, expiring join
    # code for one household — not a general bearer credential — so it's
    # looked up (and stored) directly rather than hashed.
    return secrets.token_urlsafe(24)


def generate_password_reset_token() -> str:
    # Same shape/rationale as generate_invite_token — a distinct name so
    # call sites read clearly even though the underlying generation is
    # identical.
    return secrets.token_urlsafe(24)
