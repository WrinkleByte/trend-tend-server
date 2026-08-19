import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal
from app.core.security import generate_api_token
from app.db.session import get_db
from app.models.api_token import ApiToken
from app.models.mixins import utcnow
from app.schemas.api_token import (
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
    raw_token, token_hash = generate_api_token()
    api_token = ApiToken(
        id=uuid.uuid4(),
        household_id=principal.household_id,
        user_id=principal.user_id,
        name=payload.name,
        token_hash=token_hash,
        expires_at=payload.expires_at,
    )
    db.add(api_token)
    await db.commit()
    await db.refresh(api_token)
    return ApiTokenCreateResponse.model_validate({**api_token.__dict__, "token": raw_token})


@router.get("", response_model=list[ApiTokenResponse])
async def list_api_tokens(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[ApiToken]:
    result = await db.execute(
        select(ApiToken)
        .where(ApiToken.household_id == principal.household_id, ApiToken.user_id == principal.user_id)
        .order_by(ApiToken.created_at.desc())
    )
    return list(result.scalars().all())


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
