# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import logging
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal
from app.api.v1.api_tokens import token_responses
from app.api.v1.auth import issue_refresh_token, token_response
from app.config import get_settings
from app.core.api_token_issuing import (
    app_only_email,
    issue_api_token,
    notify_key_issued_for_you,
    public_email,
    require_membership,
)
from app.core.email import send_email
from app.core.household_deletion import delete_household_data, wipe_household_data
from app.core.instance_settings import get_or_create_instance_settings
from app.core.security import (
    create_access_token,
    generate_invite_token,
)
from app.db.session import get_db
from app.models.api_token import ApiToken
from app.models.household import (
    Household,
    HouseholdInvite,
    HouseholdMembership,
    HouseholdRole,
    InviteStatus,
)
from app.models.mixins import utcnow
from app.models.user import User
from app.schemas.api_token import (
    ApiTokenCreateResponse,
    ApiTokenResponse,
    MemberApiTokenCreate,
)
from app.schemas.auth import TokenResponse
from app.schemas.household import (
    AcceptInviteRequest,
    AppOnlyMemberCreate,
    HouseholdMemberResponse,
    HouseholdResponse,
    HouseholdSettingsUpdate,
    InviteCreate,
    InviteCreateResponse,
    InvitePreviewResponse,
    InviteResponse,
)

router = APIRouter(prefix="/households", tags=["households"])
logger = logging.getLogger("app.households")

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
    return HouseholdResponse.model_validate(
        {**household.__dict__, "my_role": principal.role, "my_user_id": principal.user_id}
    )


@router.patch("/me/settings", response_model=HouseholdResponse)
async def update_household_settings(
    payload: HouseholdSettingsUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> HouseholdResponse:
    """Owner-only write side of the household admin defaults an individual
    device can locally override (see HouseholdSettingsUpdate's doc comment).
    Only the fields the caller actually set are merged in -- an unset field
    here means "leave whatever's already there," not "clear it," matching
    this endpoint's PATCH (not PUT) semantics. household.settings is a
    plain dict column (no MutableDict tracking), so the update reassigns a
    new dict rather than mutating in place -- SQLAlchemy only picks up an
    attribute reassignment, not an in-place dict mutation, as a change to
    persist."""
    _require_owner(principal)

    result = await db.execute(select(Household).where(Household.id == principal.household_id))
    household = result.scalar_one()

    updates = payload.model_dump(exclude_none=True)
    household.settings = {**household.settings, **updates}
    await db.commit()
    await db.refresh(household)
    return HouseholdResponse.model_validate(
        {**household.__dict__, "my_role": principal.role, "my_user_id": principal.user_id}
    )


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


@router.post("/me/wipe-data", status_code=status.HTTP_204_NO_CONTENT)
async def wipe_household(
    principal: Principal = Depends(get_current_principal), db: AsyncSession = Depends(get_db)
) -> None:
    """The 'start over' reset (Vikunja #27) — clears every asset, log,
    record, schedule, and attachment in the household, but the household
    itself, its members, invites, API tokens, and sync devices all survive.
    Distinct from delete_household above, which removes the household
    entirely. No undo short of restoring from a backup."""
    _require_owner(principal)
    await wipe_household_data(db, principal.household_id, principal.device_id)
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
    return [_member_response(membership, user) for membership, user in result.all()]


def _member_response(membership: HouseholdMembership, user: User) -> HouseholdMemberResponse:
    return HouseholdMemberResponse(
        user_id=user.id,
        email=public_email(user.email),
        display_name=user.display_name,
        role=membership.role,
        joined_at=membership.joined_at,
        has_login=user.password_hash is not None,
    )


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


@router.post("/members", response_model=HouseholdMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_app_only_member(
    payload: AppOnlyMemberCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> HouseholdMemberResponse:
    """Adds a family member who won't have a web account of their own: no
    password, so they can't sign in on the web; the owner pairs their phone
    with a key made for them (create_member_api_token below), and that phone
    then syncs as them. Someone who wants their own web login should get an
    invite instead (POST /invites), which this refuses to shadow: an email
    that already has an account is a 409, not a second account."""
    _require_owner(principal)

    if payload.email is not None:
        existing = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "That email already has an account. Send them an invite instead.",
            )

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=payload.email or app_only_email(user_id),
        password_hash=None,
        display_name=payload.display_name.strip(),
    )
    membership = HouseholdMembership(
        id=uuid.uuid4(),
        household_id=principal.household_id,
        user_id=user_id,
        role=payload.role,
        invited_by_user_id=principal.user_id,
    )
    # The models declare no relationship between them, so the unit of work
    # can't order the two inserts itself: flush the user before the
    # membership that references it.
    db.add(user)
    await db.flush()
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return _member_response(membership, user)


@router.post(
    "/members/{user_id}/api-tokens",
    response_model=ApiTokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_member_api_token(
    user_id: uuid.UUID,
    payload: MemberApiTokenCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ApiTokenCreateResponse:
    """The owner makes a pairing key for another member of this household,
    so a device paired with it syncs as that member (see
    app/core/api_token_issuing.py). Recorded as created by the owner, and
    the member is emailed if they have a real address."""
    _require_owner(principal)
    await require_membership(db, principal.household_id, user_id)
    api_token, raw_token = await issue_api_token(
        db,
        household_id=principal.household_id,
        user_id=user_id,
        name=payload.name,
        issued_by_user_id=principal.user_id,
        expires_at=payload.expires_at,
    )
    await notify_key_issued_for_you(db, api_token)
    return ApiTokenCreateResponse.model_validate({**api_token.__dict__, "token": raw_token})


@router.get("/members/{user_id}/api-tokens", response_model=list[ApiTokenResponse])
async def list_member_api_tokens(
    user_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[ApiTokenResponse]:
    """Every key a member has in this household, whoever made it, so the
    owner can see and revoke a lost phone's key."""
    _require_owner(principal)
    await require_membership(db, principal.household_id, user_id)
    result = await db.execute(
        select(ApiToken)
        .where(ApiToken.household_id == principal.household_id, ApiToken.user_id == user_id)
        .order_by(ApiToken.created_at.desc())
    )
    return await token_responses(db, list(result.scalars().all()))


@router.delete("/members/{user_id}/api-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_member_api_token(
    user_id: uuid.UUID,
    token_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke a member's key. Idempotent, like revoking your own."""
    _require_owner(principal)
    token = (
        await db.execute(
            select(ApiToken).where(
                ApiToken.id == token_id,
                ApiToken.household_id == principal.household_id,
                ApiToken.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if token is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API token not found")
    if token.revoked_at is None:
        token.revoked_at = utcnow()
        await db.commit()


@router.post("/invites", response_model=InviteCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    payload: InviteCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> InviteCreateResponse:
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

    email_sent = await _email_invite(db, invite, household_id=principal.household_id)
    return InviteCreateResponse.model_validate({**invite.__dict__, "email_sent": email_sent})


async def _email_invite(db: AsyncSession, invite: HouseholdInvite, *, household_id: uuid.UUID) -> bool:
    """Best-effort delivery of the join link. Returns whether it actually went
    out, so the caller can tell the owner to fall back to copying the link.

    Deliberately never raises: the invite row is already committed and the
    copy-the-link path still works, so a missing/broken SMTP relay must not
    turn a successful invite into a failed request.
    """
    join_link = f"{get_settings().frontend_url.rstrip('/')}/join?token={invite.token}"

    household = (
        await db.execute(select(Household).where(Household.id == household_id))
    ).scalar_one()
    inviter = (
        await db.execute(select(User).where(User.id == invite.created_by_user_id))
    ).scalar_one_or_none()
    inviter_name = inviter.display_name if inviter else "Someone"

    try:
        instance_settings = await get_or_create_instance_settings(db)
        # smtplib is blocking — offload so a slow or unreachable relay doesn't
        # stall the shared event loop, same as auth.py's password-reset send.
        delivered = await asyncio.to_thread(
            send_email,
            instance_settings,
            to=invite.invited_email,
            subject=f"{inviter_name} invited you to {household.name} on WrinkleByte",
            body=(
                f"{inviter_name} has invited you to join the household "
                # invite.role, not invite.role.value — the column is String(20)
                # rather than Enum, so a refreshed row hands back a plain str.
                # StrEnum and str both interpolate to the same text here.
                f'"{household.name}" on WrinkleByte as a {invite.role}.\n\n'
                f"Accept the invitation: {join_link}\n\n"
                f"This invitation expires in {INVITE_TTL_DAYS} days. "
                f"If you weren't expecting this, you can ignore this email."
            ),
        )
    except Exception:
        # send_email swallows SMTP/OS errors itself; this is the belt-and-braces
        # catch for anything else (a malformed address reaching EmailMessage,
        # say) so invite creation can't be failed by its notification.
        logger.exception("Unexpected error emailing invite %s", invite.id)
        return False

    if delivered:
        logger.info("Invite %s emailed to %s.", invite.id, invite.invited_email)
    else:
        # No token in this log line, unlike forgot-password's fallback: the
        # owner who created the invite is sitting in front of the UI with a
        # working "Copy invite link" button, so there's no need to put a
        # credential in the logs to recover delivery.
        logger.info(
            "Invite %s created for %s but no email was sent (SMTP not configured, or the "
            "send failed) — the owner can still copy the link from the household page.",
            invite.id,
            invite.invited_email,
        )
    return delivered


@router.get("/invites", response_model=list[InviteResponse])
async def list_invites(
    principal: Principal = Depends(get_current_principal), db: AsyncSession = Depends(get_db)
) -> list[HouseholdInvite]:
    """A revoked invite is never actionable again (revoke_invite below
    refuses to revoke anything already revoked, and its token can't be
    un-revoked) — excluded here so it doesn't linger in the owner's list
    forever (Vikunja #88). Pending/accepted/expired all still show: pending
    because it's actionable, accepted/expired as a useful record of what
    happened."""
    _require_owner(principal)

    result = await db.execute(
        select(HouseholdInvite)
        .where(HouseholdInvite.household_id == principal.household_id, HouseholdInvite.status != InviteStatus.REVOKED)
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
    request: Request,
    response: Response,
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
    # A tracked token (with a jti), like login issues, so it can be rotated
    # and revoked; this used to mint an untracked one that refresh had to
    # upgrade on first use.
    refresh_token = await issue_refresh_token(db, user_id=user.id, household_id=invite.household_id)
    await db.commit()

    return token_response(
        request,
        response,
        access_token=create_access_token(user_id=user.id, household_id=invite.household_id),
        refresh_token=refresh_token,
    )
