import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal
from app.core.household_deletion import delete_household_data
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_invite_token,
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
from app.schemas.auth import TokenResponse
from app.schemas.household import (
    AcceptInviteRequest,
    HouseholdMemberResponse,
    HouseholdResponse,
    InviteCreate,
    InvitePreviewResponse,
    InviteResponse,
)

router = APIRouter(prefix="/households", tags=["households"])

INVITE_TTL_DAYS = 7


def _require_owner(principal: Principal) -> None:
    if principal.role != HouseholdRole.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the household owner can do this")


@router.get("/me", response_model=HouseholdResponse)
async def get_current_household(
    principal: Principal = Depends(get_current_principal), db: AsyncSession = Depends(get_db)
) -> HouseholdResponse:
    result = await db.execute(select(Household).where(Household.id == principal.household_id))
    household = result.scalar_one()
    return HouseholdResponse.model_validate({**household.__dict__, "my_role": principal.role})


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_household(
    principal: Principal = Depends(get_current_principal), db: AsyncSession = Depends(get_db)
) -> None:
    """Permanently deletes the caller's own household and everything in it —
    every other member (including any co-owners) loses access immediately;
    their existing session tokens still decode, but the next request 403s
    at get_current_principal's membership check, same as a removed member.
    There's no undo short of restoring from a backup."""
    _require_owner(principal)
    await delete_household_data(db, principal.household_id)
    await db.commit()


@router.get("/members", response_model=list[HouseholdMemberResponse])
async def list_members(
    principal: Principal = Depends(get_current_principal), db: AsyncSession = Depends(get_db)
) -> list[HouseholdMemberResponse]:
    result = await db.execute(
        select(HouseholdMembership, User)
        .join(User, User.id == HouseholdMembership.user_id)
        .where(HouseholdMembership.household_id == principal.household_id)
        .order_by(HouseholdMembership.joined_at)
    )
    return [
        HouseholdMemberResponse(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=membership.role,
            joined_at=membership.joined_at,
        )
        for membership, user in result.all()
    ]


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_owner(principal)

    household = (
        await db.execute(select(Household).where(Household.id == principal.household_id))
    ).scalar_one()
    if household.owner_user_id == user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove the household owner")

    result = await db.execute(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == principal.household_id, HouseholdMembership.user_id == user_id
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a member of this household")

    await db.delete(membership)
    await db.commit()


@router.post("/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    payload: InviteCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> HouseholdInvite:
    _require_owner(principal)

    invite = HouseholdInvite(
        id=uuid.uuid4(),
        household_id=principal.household_id,
        invited_email=payload.invited_email,
        role=payload.role,
        token=generate_invite_token(),
        created_by_user_id=principal.user_id,
        expires_at=utcnow() + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


@router.get("/invites", response_model=list[InviteResponse])
async def list_invites(
    principal: Principal = Depends(get_current_principal), db: AsyncSession = Depends(get_db)
) -> list[HouseholdInvite]:
    _require_owner(principal)

    result = await db.execute(
        select(HouseholdInvite)
        .where(HouseholdInvite.household_id == principal.household_id)
        .order_by(HouseholdInvite.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invite_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_owner(principal)

    result = await db.execute(
        select(HouseholdInvite).where(
            HouseholdInvite.id == invite_id, HouseholdInvite.household_id == principal.household_id
        )
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    if invite.status != InviteStatus.PENDING:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only a pending invite can be revoked")

    invite.status = InviteStatus.REVOKED
    await db.commit()


@router.get("/invites/by-token/{token}", response_model=InvitePreviewResponse)
async def preview_invite(token: str, db: AsyncSession = Depends(get_db)) -> InvitePreviewResponse:
    # Deliberately unauthenticated — this is what a `/join?token=...` link
    # shows a visitor before they have an account or a session.
    result = await db.execute(
        select(HouseholdInvite, Household)
        .join(Household, Household.id == HouseholdInvite.household_id)
        .where(HouseholdInvite.token == token)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    invite, household = row
    return InvitePreviewResponse(
        household_name=household.name,
        invited_email=invite.invited_email,
        role=invite.role,
        status=invite.status,
        expires_at=invite.expires_at,
    )


@router.post("/invites/accept", response_model=TokenResponse)
async def accept_invite(
    payload: AcceptInviteRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # For an already-registered user accepting an invite to a *different*
    # household than the one their current session token is scoped to —
    # any valid session proves identity, regardless of which household it
    # names, so principal.household_id is intentionally not used here.
    result = await db.execute(select(HouseholdInvite).where(HouseholdInvite.token == payload.token))
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    if invite.status != InviteStatus.PENDING or invite.expires_at < utcnow():
        raise HTTPException(status.HTTP_410_GONE, "Invite is no longer valid")

    user = (await db.execute(select(User).where(User.id == principal.user_id))).scalar_one()
    if invite.invited_email.lower() != user.email.lower():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This invite was sent to a different email address")

    existing_membership = await db.execute(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == invite.household_id, HouseholdMembership.user_id == user.id
        )
    )
    if existing_membership.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already a member of this household")

    db.add(
        HouseholdMembership(
            id=uuid.uuid4(),
            household_id=invite.household_id,
            user_id=user.id,
            role=invite.role,
            invited_by_user_id=invite.created_by_user_id,
        )
    )
    invite.status = InviteStatus.ACCEPTED
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user_id=user.id, household_id=invite.household_id),
        refresh_token=create_refresh_token(user_id=user.id, household_id=invite.household_id),
    )
