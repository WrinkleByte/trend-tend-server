# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""The signed-in user's own profile (capability ``profile_display_name``).

Works with either kind of credential: a web session, or a device's API key,
which acts as the member it was issued to. So a phone paired for an app-only
family member changes that member's name, never its issuer's."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal
from app.core.api_token_issuing import public_email
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import MeResponse, MeUpdate

router = APIRouter(prefix="/users", tags=["users"])


def _me(user: User) -> MeResponse:
    return MeResponse(
        user_id=user.id,
        email=public_email(user.email),
        display_name=user.display_name,
        has_login=user.password_hash is not None,
    )


async def _load(db: AsyncSession, principal: Principal) -> User:
    return (
        await db.execute(select(User).where(User.id == principal.user_id))
    ).scalar_one()


@router.get("/me", response_model=MeResponse)
async def get_me(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    return _me(await _load(db, principal))


@router.patch("/me", response_model=MeResponse)
async def update_me(
    payload: MeUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    user = await _load(db, principal)
    if payload.display_name is not None:
        user.display_name = payload.display_name
    await db.commit()
    await db.refresh(user)
    return _me(user)
