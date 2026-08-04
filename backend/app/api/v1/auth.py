import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.household import (
    Household,
    HouseholdInvite,
    HouseholdMembership,
    HouseholdRole,
    InviteStatus,
)
from app.models.mixins import utcnow
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _consume_pending_invite(db: AsyncSession, token: str, email: str) -> HouseholdInvite:
    result = await db.execute(select(HouseholdInvite).where(HouseholdInvite.token == token))
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    if invite.status != InviteStatus.PENDING or invite.expires_at < utcnow():
        raise HTTPException(status.HTTP_410_GONE, "Invite is no longer valid")
    if invite.invited_email.lower() != email.lower():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This invite was sent to a different email address")
    return invite


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    invite = (
        await _consume_pending_invite(db, payload.invite_token, payload.email) if payload.invite_token else None
    )

    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    await db.flush()

    if invite is not None:
        household_id = invite.household_id
        db.add(
            HouseholdMembership(
                id=uuid.uuid4(),
                household_id=household_id,
                user_id=user.id,
                role=invite.role,
                invited_by_user_id=invite.created_by_user_id,
            )
        )
        invite.status = InviteStatus.ACCEPTED
    else:
        household = Household(id=uuid.uuid4(), name=payload.household_name, owner_user_id=user.id, settings={})
        db.add(household)
        await db.flush()
        household_id = household.id
        db.add(
            HouseholdMembership(
                id=uuid.uuid4(),
                household_id=household_id,
                user_id=user.id,
                role=HouseholdRole.OWNER,
            )
        )

    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user_id=user.id, household_id=household_id),
        refresh_token=create_refresh_token(user_id=user.id, household_id=household_id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, household_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or user.password_hash is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    memberships_result = await db.execute(
        select(HouseholdMembership)
        .where(HouseholdMembership.user_id == user.id)
        .order_by(HouseholdMembership.joined_at)
    )
    memberships = memberships_result.scalars().all()
    if not memberships:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User belongs to no household")

    if household_id is not None:
        selected = next((m for m in memberships if m.household_id == household_id), None)
        if selected is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of the requested household")
    else:
        selected = memberships[0]

    return TokenResponse(
        access_token=create_access_token(user_id=user.id, household_id=selected.household_id),
        refresh_token=create_refresh_token(user_id=user.id, household_id=selected.household_id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest) -> TokenResponse:
    try:
        claims = decode_token(payload.refresh_token)
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token") from exc
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")

    user_id = uuid.UUID(claims["sub"])
    household_id = uuid.UUID(claims["household_id"])
    return TokenResponse(
        access_token=create_access_token(user_id=user_id, household_id=household_id),
        refresh_token=create_refresh_token(user_id=user_id, household_id=household_id),
    )
