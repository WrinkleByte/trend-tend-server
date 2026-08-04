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
    token = await _get_owned_token(db, principal, token_id)
    token.revoked_at = utcnow()
    await db.commit()
