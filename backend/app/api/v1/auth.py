import asyncio
import logging
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import reject_if_token_predates_invalidation
from app.config import get_settings
from app.core.email import send_email
from app.core.instance_settings import get_or_create_instance_settings
from app.core.rate_limit import RateLimiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_password_reset_token,
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
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SetupStatusResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("app.auth")

# Reset links are short-lived on purpose — this only needs to survive one
# email round-trip, not sit in an inbox indefinitely as a standing risk.
PASSWORD_RESET_TOKEN_TTL = timedelta(hours=1)

# Baseline brute-force/credential-stuffing defense (Vikunja #35) — these
# four endpoints are the only unauthenticated, password-adjacent surface
# on an internet-facing-by-design app. Keyed by IP rather than by
# account/email: locking an *account* out after N failures is its own
# denial-of-service vector (anyone who knows a victim's email address
# could lock them out), so IP is the standard baseline instead. A
# separate instance per endpoint rather than one shared limiter — login
# and register are different threat models (credential stuffing vs. spam
# signups), and a real user's own register call shouldn't eat into their
# own login budget. forgot-password/reset-password get a stricter,
# longer-window limit since they're higher-value (email enumeration,
# account takeover) than a login attempt.
_login_limiter = RateLimiter(times=10, seconds=60)
_register_limiter = RateLimiter(times=10, seconds=60)
_forgot_password_limiter = RateLimiter(times=5, seconds=300)
_reset_password_limiter = RateLimiter(times=5, seconds=300)
# Refresh was the one unauthenticated auth endpoint with no limiter at all
# (review S12), despite accepting a long-lived credential. Looser than
# login: legitimate clients refresh on a timer, so the ceiling only needs
# to stop bulk token-grinding, not normal use.
_refresh_limiter = RateLimiter(times=30, seconds=60)

# Verified against when no user matches, purely so the timing of a failed
# login doesn't reveal whether the account exists (review S10). Computed once
# at import rather than per-request -- hashing here would itself cost a full
# Argon2 round on every miss. The plaintext is irrelevant and unusable: no
# user row carries this hash, so it can never authenticate anything.
DUMMY_PASSWORD_HASH = hash_password("timing-equalisation-only-never-a-real-password")


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


@router.get("/setup-status", response_model=SetupStatusResponse)
async def setup_status(db: AsyncSession = Depends(get_db)) -> SetupStatusResponse:
    """Unauthenticated by design — a freshly-deployed instance has no user
    yet, so nothing could call this with credentials. Clients use it to
    decide whether to show a normal login form or a first-run "Create
    Admin Account" screen."""
    result = await db.execute(select(func.count()).select_from(User))
    return SetupStatusResponse(setup_complete=result.scalar_one() > 0)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_register_limiter),
) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    invite = (
        await _consume_pending_invite(db, payload.invite_token, payload.email) if payload.invite_token else None
    )

    # Whoever registers first — on a fresh instance with zero users — becomes
    # the instance admin (see User.is_instance_admin's doc comment). This
    # check-then-insert has the same benign race as get_or_create_instance_settings:
    # a self-hosted single-family deployment's first two requests landing in
    # the same instant is not a scenario worth an advisory lock over.
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()

    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        is_instance_admin=(user_count == 0),
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
    payload: LoginRequest,
    household_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_login_limiter),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    # Verify against a dummy hash when there's no such user, so both paths pay
    # the same Argon2 cost (review S10). Argon2 is deliberately slow, so
    # skipping it for unknown emails made "no such account" measurably faster
    # than "wrong password" -- a clean timing oracle for which addresses are
    # registered, which undercuts the care forgot_password takes below to
    # avoid leaking exactly that.
    if user is None or user.password_hash is None:
        verify_password(payload.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not verify_password(payload.password, user.password_hash):
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
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_refresh_limiter),
) -> TokenResponse:
    try:
        claims = decode_token(payload.refresh_token)
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token") from exc
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")

    user_id = uuid.UUID(claims["sub"])
    household_id = uuid.UUID(claims["household_id"])

    # A refresh token outlives an access token by 30 days to 15 minutes, so
    # it's the credential worth stealing -- it must respect the same
    # invalidation cutoff a password reset sets, or resetting would evict
    # only the short-lived half of a compromised session (review S5/S6).
    await reject_if_token_predates_invalidation(db, user_id, claims)

    return TokenResponse(
        access_token=create_access_token(user_id=user_id, household_id=household_id),
        refresh_token=create_refresh_token(user_id=user_id, household_id=household_id),
    )


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_forgot_password_limiter),
) -> dict:
    """Always returns 200 with the same generic body regardless of whether
    the email matches an account — a distinguishable response here would
    let anyone enumerate which addresses are registered."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is not None:
        reset_token = PasswordResetToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token=generate_password_reset_token(),
            expires_at=utcnow() + PASSWORD_RESET_TOKEN_TTL,
        )
        db.add(reset_token)
        await db.commit()

        # The token by itself isn't something a user can do anything with —
        # it's a URL query param for ResetPasswordPage.tsx, not a password.
        # Logged unconditionally (not just on send failure) so an admin can
        # still hand someone this link manually from the logs, e.g. before
        # SMTP is configured on a fresh install.
        reset_link = f"{get_settings().frontend_url.rstrip('/')}/reset-password?token={reset_token.token}"
        logger.info("Password reset requested for %s: %s", user.email, reset_link)

        instance_settings = await get_or_create_instance_settings(db)
        # smtplib is blocking — offload so this request (and the shared
        # event loop) doesn't stall on a slow/unreachable SMTP relay.
        await asyncio.to_thread(
            send_email,
            instance_settings,
            to=user.email,
            subject="Reset your WrinkleByte password",
            body=(
                f"Someone requested a password reset for this account.\n\n"
                f"Reset your password: {reset_link}\n\n"
                f"This link expires in 1 hour. If you didn't request this, ignore this email."
            ),
        )

    return {"detail": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_reset_password_limiter),
) -> dict:
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token == payload.token))
    reset_token = result.scalar_one_or_none()
    if reset_token is None or reset_token.used_at is not None or reset_token.expires_at < utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    now = utcnow()
    user.password_hash = hash_password(payload.new_password)
    reset_token.used_at = now
    # Evict every existing session (2026-08-19 review, S5). Without this, a
    # reset changed the password but left previously-issued tokens working --
    # refresh tokens for up to 30 days. Since the usual reason to reset is a
    # suspected compromise, the one action a user takes to lock an attacker
    # out did not actually do so.
    user.tokens_valid_after = now

    # Any other outstanding reset tokens for this user are burned too --
    # otherwise an older reset email remains a live path to the account.
    other_tokens = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    for token in other_tokens.scalars():
        token.used_at = now

    await db.commit()

    return {"detail": "Password reset successfully."}
