import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, hash_api_token, is_api_token
from app.db.session import get_db
from app.models.api_token import ApiToken
from app.models.household import HouseholdMembership
from app.models.mixins import utcnow
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    """The resolved identity of a request, regardless of which auth mechanism
    produced it — endpoints consume this and never know whether the caller
    authenticated via a session JWT or a paired API key."""

    user_id: uuid.UUID
    household_id: uuid.UUID
    role: str
    device_id: uuid.UUID | None


async def _get_membership(
    db: AsyncSession, user_id: uuid.UUID, household_id: uuid.UUID
) -> HouseholdMembership:
    result = await db.execute(
        select(HouseholdMembership).where(
            HouseholdMembership.user_id == user_id,
            HouseholdMembership.household_id == household_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this household")
    return membership


async def reject_if_token_predates_invalidation(
    db: AsyncSession, user_id: uuid.UUID, payload: dict
) -> None:
    """Enforce User.tokens_valid_after against a JWT's issued-at claim.

    Password reset bumps that column, which is what makes every token issued
    before the reset stop working -- see the field's comment in models/user.py.
    Applies to JWTs only; API keys carry their own explicit revoked_at.
    """
    result = await db.execute(select(User.tokens_valid_after).where(User.id == user_id))
    cutoff = result.scalar_one_or_none()
    if cutoff is None:
        return

    issued_at = payload.get("iat")
    if issued_at is None:
        # Pre-dates the claim being set, so it cannot be proven to post-date
        # the invalidation -- refuse rather than assume in the token's favour.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is no longer valid")

    issued = datetime.fromtimestamp(issued_at, tz=UTC)
    # `iat` has whole-second resolution while the cutoff is microsecond-
    # precise, so a token minted in the same second as the reset would
    # otherwise survive it. Compare on that boundary rather than exactly.
    if issued < cutoff.replace(microsecond=0):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is no longer valid")


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing credentials")
    token = credentials.credentials

    if is_api_token(token):
        result = await db.execute(
            select(ApiToken).where(ApiToken.token_hash == hash_api_token(token))
        )
        api_token = result.scalar_one_or_none()
        if api_token is None or api_token.revoked_at is not None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key"
            )
        if api_token.expires_at is not None and api_token.expires_at < utcnow():
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Expired API key")
        api_token.last_used_at = utcnow()
        await db.commit()
        membership = await _get_membership(
            db, api_token.user_id, api_token.household_id
        )
        return Principal(
            user_id=api_token.user_id,
            household_id=api_token.household_id,
            role=membership.role,
            device_id=None,
        )

    try:
        payload = decode_token(token)
    except pyjwt.PyJWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired token"
        ) from exc
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")

    user_id = uuid.UUID(payload["sub"])
    household_id = uuid.UUID(payload["household_id"])
    device_id = uuid.UUID(payload["device_id"]) if payload.get("device_id") else None
    await reject_if_token_predates_invalidation(db, user_id, payload)
    membership = await _get_membership(db, user_id, household_id)
    return Principal(
        user_id=user_id,
        household_id=household_id,
        role=membership.role,
        device_id=device_id,
    )


async def require_instance_admin(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    """Gates instance-wide settings (SMTP, etc.) — deliberately a separate
    dependency rather than a field on Principal, since checking
    is_instance_admin needs a User-table lookup that every other endpoint
    (the overwhelming majority of requests) has no reason to pay for."""
    result = await db.execute(
        select(User.is_instance_admin).where(User.id == principal.user_id)
    )
    is_admin = result.scalar_one_or_none()
    if not is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Instance admin access required")
    return principal


def household_scoped_query(model, principal: Principal):
    """Every household-scoped query should be built from this helper rather
    than hand-rolling the filter, so tenant isolation is structurally hard to
    forget rather than a convention any single handler could skip."""
    return select(model).where(
        model.household_id == principal.household_id, model.deleted_at.is_(None)
    )


async def verify_owned_reference(
    db: AsyncSession, principal: Principal, model, ref_id: uuid.UUID, label: str
) -> None:
    """Guards a client-supplied foreign key (e.g. a fuel log's asset_id, or
    a maintenance record's schedule_id) against pointing at another
    household's row. Unlike an endpoint's own primary resource -- which
    always goes through household_scoped_query, so a mismatched id 404s
    automatically -- a *referenced* id on create/update is just a bare UUID
    in the payload with nothing forcing it through that same check unless
    each call site remembers to do it. Raises 404 (not 403) so a
    foreign-household id is indistinguishable from a nonexistent one,
    matching every other "not found vs not yours" response in this API.
    """
    result = await db.execute(
        select(model.id).where(
            model.id == ref_id,
            model.household_id == principal.household_id,
            model.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found")
