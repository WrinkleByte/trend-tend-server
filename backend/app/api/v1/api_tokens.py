# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal
from app.core.api_token_issuing import (
    issue_api_token,
    notify_key_issued_for_you,
    require_membership,
)
from app.db.session import get_db
from app.models.api_token import ApiToken
from app.models.household import HouseholdRole
from app.models.mixins import utcnow
from app.models.user import User
from app.schemas.api_token import (
    ApiTokenAssign,
    ApiTokenCreate,
    ApiTokenCreateResponse,
    ApiTokenResponse,
)

router = APIRouter(prefix="/api-tokens", tags=["api-tokens"])


@router.post("", response_model=ApiTokenCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_token(
    payload: ApiTokenCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ApiTokenCreateResponse:
    api_token, raw_token = await issue_api_token(
        db,
        household_id=principal.household_id,
        user_id=principal.user_id,
        name=payload.name,
        issued_by_user_id=principal.user_id,
        expires_at=payload.expires_at,
    )
    return ApiTokenCreateResponse.model_validate({**api_token.__dict__, "token": raw_token})


async def token_responses(db: AsyncSession, tokens: list[ApiToken]) -> list[ApiTokenResponse]:
    """ApiTokenResponse for each key, with created_by_name filled in, so a
    person can see "Created by Adam" on a key someone else made for them."""
    issuer_ids = {t.created_by_user_id for t in tokens if t.created_by_user_id}
    names: dict[uuid.UUID, str] = {}
    if issuer_ids:
        rows = await db.execute(select(User.id, User.display_name).where(User.id.in_(issuer_ids)))
        names = {user_id: display_name for user_id, display_name in rows.all()}
    return [
        ApiTokenResponse.model_validate(t).model_copy(
            update={"created_by_name": names.get(t.created_by_user_id) if t.created_by_user_id else None}
        )
        for t in tokens
    ]


@router.get("", response_model=list[ApiTokenResponse])
async def list_api_tokens(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[ApiTokenResponse]:
    result = await db.execute(
        select(ApiToken)
        .where(ApiToken.household_id == principal.household_id, ApiToken.user_id == principal.user_id)
        .order_by(ApiToken.created_at.desc())
    )
    return await token_responses(db, list(result.scalars().all()))


async def _get_owned_token(db: AsyncSession, principal: Principal, token_id: uuid.UUID) -> ApiToken:
    result = await db.execute(
        select(ApiToken).where(
            ApiToken.id == token_id,
            ApiToken.household_id == principal.household_id,
            ApiToken.user_id == principal.user_id,
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API token not found")
    return token


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_token(
    token_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke a token. Idempotent -- re-revoking is a no-op, not an error."""
    token = await _get_owned_token(db, principal, token_id)
    if token.revoked_at is None:
        token.revoked_at = utcnow()
        await db.commit()


@router.delete("/{token_id}/permanently", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_token(
    token_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a revoked token's row entirely (Vikunja #26).

    Revoking is the security action and is enough to make a token useless;
    this is the housekeeping one, so that revoked tokens don't accumulate in
    the list forever with no way to clear them.

    **Revoke-first is enforced**, not merely suggested: allowing a live token
    to be deleted in one step would make it trivially easy to destroy the
    audit trail of a credential that was in use, and would remove the moment
    where someone can notice they revoked the wrong one. The client must
    revoke, see the effect, and then choose to tidy up.
    """
    token = await _get_owned_token(db, principal, token_id)
    if token.revoked_at is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Revoke this token before deleting it.",
        )
    await db.delete(token)
    await db.commit()


@router.patch("/{token_id}", response_model=ApiTokenResponse)
async def assign_api_token(
    token_id: uuid.UUID,
    payload: ApiTokenAssign,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ApiTokenResponse:
    """Move an existing key to another member of the household (Vikunja #165):
    a phone already paired with the owner's key becomes Kate's phone without
    re-pairing. The key isn't tied to a device server-side, and the apps
    re-read "who am I" (households/me's my_user_id) on every sync, so the
    device acts as the new user from its next sync on.

    Owner only, for any key in the household: letting a member hand their
    own key to someone else would leave them holding a working copy that
    acts as that person. Recorded the same way as a key made for someone
    (created_by = the owner, unless it's assigned back to the owner
    themselves), and the new holder is emailed if they have a real address.
    """
    if principal.role != HouseholdRole.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the household owner can do this")
    token = (
        await db.execute(
            select(ApiToken).where(ApiToken.id == token_id, ApiToken.household_id == principal.household_id)
        )
    ).scalar_one_or_none()
    if token is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API token not found")
    if token.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This key is revoked; make a new one instead.")
    await require_membership(db, principal.household_id, payload.user_id)

    if token.user_id != payload.user_id:
        token.user_id = payload.user_id
        token.created_by_user_id = None if payload.user_id == principal.user_id else principal.user_id
        await db.commit()
        await db.refresh(token)
        await notify_key_issued_for_you(db, token)
    return (await token_responses(db, [token]))[0]
