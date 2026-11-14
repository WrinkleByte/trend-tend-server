# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""Issuing API keys (pairing codes), for yourself or for another member.

A device syncs as whichever user its API key belongs to (get_current_principal
resolves the key to that user). So the three callers differ only in who may
ask, and these helpers are shared by all of them:

- api_tokens.py: any user, for themselves.
- households.py: a household owner, for a member of their own household, so
  a family can pair everyone's phone without each person needing a web login.
- admin.py: an instance admin, for any member of any household.

Issuing a key for someone else is deliberately a form of impersonation: the
device acts as that person. Hence created_by_user_id (shown to the person in
their own key list) and the best-effort email to them when they have a real
address.
"""

import asyncio
import logging
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import send_email
from app.core.instance_settings import get_or_create_instance_settings
from app.core.security import generate_api_token
from app.models.api_token import ApiToken
from app.models.household import Household, HouseholdMembership
from app.models.user import User

logger = logging.getLogger("app.api_tokens")

# Members added without an email address (a child, a spouse who only uses the
# app) still need a unique users.email. They get an address under the
# reserved .invalid TLD (RFC 2606), which can never receive mail or collide
# with a real one, and is never shown: see public_email().
APP_ONLY_EMAIL_DOMAIN = "app-only.invalid"


def app_only_email(user_id: uuid.UUID) -> str:
    return f"member-{user_id.hex}@{APP_ONLY_EMAIL_DOMAIN}"


def is_app_only_email(email: str) -> bool:
    return email.lower().endswith("@" + APP_ONLY_EMAIL_DOMAIN)


def public_email(email: str) -> str:
    """The address to show people: the real one, or "" for an app-only member."""
    return "" if is_app_only_email(email) else email


async def require_membership(db: AsyncSession, household_id: uuid.UUID, user_id: uuid.UUID) -> HouseholdMembership:
    """A key is household-scoped, so it may only be issued to a member of
    that household. 404 rather than 403 so a caller can't probe which user
    ids exist elsewhere."""
    membership = (
        await db.execute(
            select(HouseholdMembership).where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a member of this household")
    return membership


async def issue_api_token(
    db: AsyncSession,
    *,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    issued_by_user_id: uuid.UUID,
    expires_at: datetime | None = None,
) -> tuple[ApiToken, str]:
    """Creates and commits a key; returns it with the raw token, which is
    never stored and can't be shown again. created_by_user_id is only set
    when someone issued it for another person."""
    raw_token, token_hash = generate_api_token()
    api_token = ApiToken(
        id=uuid.uuid4(),
        household_id=household_id,
        user_id=user_id,
        created_by_user_id=None if issued_by_user_id == user_id else issued_by_user_id,
        name=name,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(api_token)
    await db.commit()
    await db.refresh(api_token)
    return api_token, raw_token


async def notify_key_issued_for_you(db: AsyncSession, api_token: ApiToken) -> bool:
    """Best-effort email telling a person that someone else made a pairing
    key in their name. Never raises (the key already exists and works), and
    skips app-only members, who have no address to tell."""
    if api_token.created_by_user_id is None:
        return False
    target = (await db.execute(select(User).where(User.id == api_token.user_id))).scalar_one()
    if is_app_only_email(target.email):
        return False
    issuer = (
        await db.execute(select(User).where(User.id == api_token.created_by_user_id))
    ).scalar_one_or_none()
    household = (
        await db.execute(select(Household).where(Household.id == api_token.household_id))
    ).scalar_one()
    issuer_name = issuer.display_name if issuer else "An administrator"
    try:
        instance_settings = await get_or_create_instance_settings(db)
        return await asyncio.to_thread(
            send_email,
            instance_settings,
            to=target.email,
            subject=f"{issuer_name} set up a device for you on WrinkleByte",
            body=(
                f'{issuer_name} created a pairing key named "{api_token.name}" for you in the '
                f'household "{household.name}". A phone or tablet paired with it syncs as you.\n\n'
                "If that's expected, there's nothing to do. If not, you can see and revoke it "
                "under Settings > API Tokens in the web app, or ask the household owner."
            ),
        )
    except Exception:
        logger.exception("Unexpected error emailing key-issued notice for token %s", api_token.id)
        return False
