import uuid
from dataclasses import dataclass

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


async def _get_membership(db: AsyncSession, user_id: uuid.UUID, household_id: uuid.UUID) -> HouseholdMembership:
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


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing credentials")
    token = credentials.credentials

    if is_api_token(token):
        result = await db.execute(select(ApiToken).where(ApiToken.token_hash == hash_api_token(token)))
        api_token = result.scalar_one_or_none()
        if api_token is None or api_token.revoked_at is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key")
        if api_token.expires_at is not None and api_token.expires_at < utcnow():
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Expired API key")
        api_token.last_used_at = utcnow()
        await db.commit()
        membership = await _get_membership(db, api_token.user_id, api_token.household_id)
        return Principal(
            user_id=api_token.user_id,
            household_id=api_token.household_id,
            role=membership.role,
            device_id=None,
        )

    try:
        payload = decode_token(token)
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")

    user_id = uuid.UUID(payload["sub"])
    household_id = uuid.UUID(payload["household_id"])
    device_id = uuid.UUID(payload["device_id"]) if payload.get("device_id") else None
    membership = await _get_membership(db, user_id, household_id)
    return Principal(user_id=user_id, household_id=household_id, role=membership.role, device_id=device_id)


async def require_instance_admin(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    """Gates instance-wide settings (SMTP, etc.) — deliberately a separate
    dependency rather than a field on Principal, since checking
    is_instance_admin needs a User-table lookup that every other endpoint
    (the overwhelming majority of requests) has no reason to pay for."""
    result = await db.execute(select(User.is_instance_admin).where(User.id == principal.user_id))
    is_admin = result.scalar_one_or_none()
    if not is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Instance admin access required")
    return principal


def household_scoped_query(model, principal: Principal):
    """Every household-scoped query should be built from this helper rather
    than hand-rolling the filter, so tenant isolation is structurally hard to
    forget rather than a convention any single handler could skip."""
    return select(model).where(model.household_id == principal.household_id, model.deleted_at.is_(None))
