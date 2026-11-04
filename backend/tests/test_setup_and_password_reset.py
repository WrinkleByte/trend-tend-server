# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

from datetime import timedelta

from sqlalchemy import select

from app.models.instance_settings import InstanceSettings
from app.models.mixins import utcnow
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User


async def _register(client, email: str, household_name: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "a very good password",
            "display_name": email.split("@")[0],
            "household_name": household_name,
        },
    )
    assert response.status_code == 201
    return response.json()


# ===== setup-status / first-user-is-admin =====


# These two assert on the one field they're about rather than the whole
# payload — setup-status now also carries allow_self_registration (see the
# registration-toggle tests at the bottom of this file), and an exact-dict
# comparison makes every future addition to this response a false failure.
async def test_setup_status_false_before_any_user_exists(client):
    response = await client.get("/api/v1/auth/setup-status")
    assert response.status_code == 200
    assert response.json()["setup_complete"] is False


async def test_setup_status_true_after_first_user_registers(client):
    await _register(client, "first@example.com", "First House")
    response = await client.get("/api/v1/auth/setup-status")
    assert response.json()["setup_complete"] is True


async def test_first_registered_user_becomes_instance_admin(client, db_session):
    await _register(client, "first@example.com", "First House")

    result = await db_session.execute(select(User).where(User.email == "first@example.com"))
    user = result.scalar_one()
    assert user.is_instance_admin is True


async def test_second_registered_user_is_not_instance_admin(client, db_session):
    await _register(client, "first@example.com", "First House")
    await _register(client, "second@example.com", "Second House")

    result = await db_session.execute(select(User).where(User.email == "second@example.com"))
    user = result.scalar_one()
    assert user.is_instance_admin is False


# ===== forgot-password / reset-password =====


async def test_forgot_password_unknown_email_still_returns_200(client):
    response = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert response.status_code == 200
    assert "detail" in response.json()


async def test_forgot_password_known_email_creates_reset_token(client, db_session):
    await _register(client, "alice@example.com", "Alice's House")

    response = await client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
    assert response.status_code == 200

    user_result = await db_session.execute(select(User).where(User.email == "alice@example.com"))
    user = user_result.scalar_one()
    token_result = await db_session.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    token = token_result.scalar_one()
    assert token.used_at is None
    assert token.expires_at > utcnow()


async def test_forgot_password_falls_back_to_logging_the_link_when_send_actually_fails(
    client, db_session, monkeypatch, caplog
):
    """Regression for Vikunja #101: a user with fully-configured-looking SMTP
    (host/port/credentials all present) whose actual send fails -- a bad
    password, a relay rejecting the connection, etc. -- must still get a
    logged fallback link. Previously the log decision was made from
    smtp_can_deliver() (config presence only, checked before ever attempting
    the send), so a real send failure here was swallowed silently: no email,
    and no logged link either, leaving the user with no way to complete a
    reset at all."""
    await _register(client, "alice@example.com", "Alice's House")

    monkeypatch.setattr("app.api.v1.auth.send_email", lambda *args, **kwargs: False)

    with caplog.at_level("WARNING"):
        response = await client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
    assert response.status_code == 200

    user_result = await db_session.execute(select(User).where(User.email == "alice@example.com"))
    user = user_result.scalar_one()
    token_result = await db_session.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    token = token_result.scalar_one()

    warning_messages = [record.getMessage() for record in caplog.records if record.levelname == "WARNING"]
    assert any(token.token in message for message in warning_messages)


async def test_reset_password_with_valid_token_changes_password(client, db_session):
    await _register(client, "alice@example.com", "Alice's House")
    await client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})

    user_result = await db_session.execute(select(User).where(User.email == "alice@example.com"))
    user = user_result.scalar_one()
    token_result = await db_session.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    token = token_result.scalar_one()

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token.token, "new_password": "a brand new password"},
    )
    assert response.status_code == 200

    old_login = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "a very good password"}
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "a brand new password"}
    )
    assert new_login.status_code == 200


async def test_reset_password_token_is_single_use(client, db_session):
    await _register(client, "alice@example.com", "Alice's House")
    await client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})

    user_result = await db_session.execute(select(User).where(User.email == "alice@example.com"))
    user = user_result.scalar_one()
    token_result = await db_session.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    token = token_result.scalar_one()

    first = await client.post(
        "/api/v1/auth/reset-password", json={"token": token.token, "new_password": "first new password"}
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/auth/reset-password", json={"token": token.token, "new_password": "second new password"}
    )
    assert second.status_code == 400


async def test_reset_password_expired_token_rejected(client, db_session):
    await _register(client, "alice@example.com", "Alice's House")
    await client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})

    user_result = await db_session.execute(select(User).where(User.email == "alice@example.com"))
    user = user_result.scalar_one()
    token_result = await db_session.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    token = token_result.scalar_one()
    token.expires_at = utcnow() - timedelta(minutes=1)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/reset-password", json={"token": token.token, "new_password": "irrelevant but long enough"}
    )
    assert response.status_code == 400


async def test_reset_password_garbage_token_rejected(client):
    response = await client.post(
        "/api/v1/auth/reset-password", json={"token": "not-a-real-token", "new_password": "irrelevant but long enough"}
    )
    assert response.status_code == 400


# ===== instance settings (SMTP config) =====


async def test_instance_settings_requires_auth(client):
    response = await client.get("/api/v1/instance-settings")
    assert response.status_code == 401


async def test_instance_settings_requires_admin(client, auth_headers, db_session):
    # `registered_user`/`auth_headers` (from conftest) is alice@example.com,
    # the FIRST user registered in this test's isolated DB — so she'd
    # normally be the instance admin. Explicitly demote her to exercise the
    # non-admin-rejected path realistically (a second/later household user).
    result = await db_session.execute(select(User).where(User.email == "alice@example.com"))
    user = result.scalar_one()
    user.is_instance_admin = False
    await db_session.commit()

    response = await client.get("/api/v1/instance-settings", headers=auth_headers)
    assert response.status_code == 403


async def test_instance_admin_can_read_and_write_smtp_settings(client, auth_headers):
    # registered_user is the first (and only, until this test) user, so she
    # holds is_instance_admin already via the first-user-is-admin rule.
    get_response = await client.get("/api/v1/instance-settings", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["smtp_enabled"] is False
    assert get_response.json()["smtp_password_set"] is False

    put_response = await client.put(
        "/api/v1/instance-settings",
        headers=auth_headers,
        json={
            "smtp_enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "relay-user",
            "smtp_password": "relay-secret",
            "smtp_use_tls": True,
            "smtp_from_address": "no-reply@example.com",
        },
    )
    assert put_response.status_code == 200
    body = put_response.json()
    assert body["smtp_enabled"] is True
    assert body["smtp_host"] == "smtp.example.com"
    assert body["smtp_password_set"] is True
    assert "smtp_password" not in body


async def test_instance_settings_password_omitted_leaves_it_unchanged(client, auth_headers):
    await client.put(
        "/api/v1/instance-settings",
        headers=auth_headers,
        json={"smtp_password": "original-secret"},
    )

    response = await client.put(
        "/api/v1/instance-settings",
        headers=auth_headers,
        json={"smtp_host": "smtp2.example.com"},
    )
    assert response.status_code == 200
    assert response.json()["smtp_password_set"] is True
    assert response.json()["smtp_host"] == "smtp2.example.com"


async def test_instance_settings_empty_string_clears_password(client, auth_headers):
    await client.put(
        "/api/v1/instance-settings",
        headers=auth_headers,
        json={"smtp_password": "original-secret"},
    )

    response = await client.put(
        "/api/v1/instance-settings",
        headers=auth_headers,
        json={"smtp_password": ""},
    )
    assert response.status_code == 200
    assert response.json()["smtp_password_set"] is False


async def test_get_or_create_instance_settings_is_a_true_singleton(client, auth_headers, db_session):
    await client.get("/api/v1/instance-settings", headers=auth_headers)
    await client.get("/api/v1/instance-settings", headers=auth_headers)

    result = await db_session.execute(select(InstanceSettings))
    rows = result.scalars().all()
    assert len(rows) == 1


# --- Password reset must evict existing sessions (review S5/S6) ---
#
# Reset previously changed the password but left every already-issued token
# working -- refresh tokens for up to 30 days. Since the usual reason to
# reset is a suspected compromise, the one action a user takes to lock an
# attacker out did not actually do so.


async def _reset_token_for(db_session, user_email: str) -> str:
    from sqlalchemy import select

    from app.models.password_reset_token import PasswordResetToken
    from app.models.user import User

    user = (await db_session.execute(select(User).where(User.email == user_email))).scalar_one()
    token = (
        await db_session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .order_by(PasswordResetToken.expires_at.desc())
        )
    ).scalars().first()
    return token.token


async def test_password_reset_invalidates_existing_access_token(client, db_session):
    email = "evict-access@example.com"
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "the original password",
            "display_name": "Evict",
            "household_name": "Evict House",
        },
    )
    stolen_headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    # The stolen token works before the reset.
    assert (await client.get("/api/v1/assets", headers=stolen_headers)).status_code == 200

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    token = await _reset_token_for(db_session, email)
    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "a completely new password"},
    )
    assert reset.status_code == 200

    # ...and must not afterwards.
    assert (await client.get("/api/v1/assets", headers=stolen_headers)).status_code == 401


async def test_password_reset_invalidates_existing_refresh_token(client, db_session):
    email = "evict-refresh@example.com"
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "the original password",
            "display_name": "Evict",
            "household_name": "Evict House 2",
        },
    )
    stolen_refresh = register.json()["refresh_token"]

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    token = await _reset_token_for(db_session, email)
    await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "a completely new password"},
    )

    # The refresh token is the credential worth stealing -- 30 days vs 15
    # minutes -- so it must not survive the reset either.
    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": stolen_refresh})
    assert refreshed.status_code == 401


async def test_login_after_reset_still_works(client, db_session):
    # The eviction must not lock out the legitimate user.
    email = "evict-login@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "the original password",
            "display_name": "Evict",
            "household_name": "Evict House 3",
        },
    )
    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    token = await _reset_token_for(db_session, email)
    await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "a completely new password"},
    )

    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "a completely new password"}
    )
    assert login.status_code == 200
    fresh_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get("/api/v1/assets", headers=fresh_headers)).status_code == 200


# --- Password policy (review S4) ---


async def test_register_rejects_a_short_password(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "short@example.com",
            "password": "short",
            "display_name": "Short",
            "household_name": "Short House",
        },
    )
    assert response.status_code == 422


async def test_reset_rejects_a_short_password(client, db_session):
    email = "short-reset@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "the original password",
            "display_name": "Short",
            "household_name": "Short House 2",
        },
    )
    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    token = await _reset_token_for(db_session, email)
    response = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "short"}
    )
    assert response.status_code == 422


async def test_login_does_not_apply_the_length_policy(client):
    # Pre-policy accounts must still be able to log in (and then change it),
    # and the login schema must not advertise the policy's bounds.
    response = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert response.status_code == 401


# --- Refresh-token rotation with reuse detection (review S6) ---


async def _register(client, email: str, household: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "a very good password",
            "display_name": "Rotate",
            "household_name": household,
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_refresh_rotates_the_token(client):
    tokens = await _register(client, "rotate-1@example.com", "Rotate House 1")
    first = tokens["refresh_token"]

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert refreshed.status_code == 200
    second = refreshed.json()["refresh_token"]
    assert second != first, "refresh must issue a NEW token, not hand back the same one"

    # The new one works.
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": second})).status_code == 200


async def test_reusing_a_spent_refresh_token_is_rejected(client):
    tokens = await _register(client, "rotate-2@example.com", "Rotate House 2")
    first = tokens["refresh_token"]

    await client.post("/api/v1/auth/refresh", json={"refresh_token": first})

    # Replaying the now-spent token must fail -- this is the theft signal.
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401


async def test_reuse_revokes_the_whole_family(client):
    """The point of reuse detection: the attacker's *current* token dies too.

    Detecting the replay but leaving the freshly-rotated token alive would
    be useless -- whoever replayed already holds the newer one.
    """
    tokens = await _register(client, "rotate-3@example.com", "Rotate House 3")
    stolen = tokens["refresh_token"]

    rotated = (await client.post("/api/v1/auth/refresh", json={"refresh_token": stolen})).json()[
        "refresh_token"
    ]
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": rotated})).status_code == 200

    # Now the attacker replays the original, spent token.
    latest = (await client.post("/api/v1/auth/refresh", json={"refresh_token": rotated})).status_code
    assert latest == 401  # rotated was itself spent by the call above

    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": stolen})
    assert replay.status_code == 401

    # Every token in the family is now dead, including the most recent one.
    for token in (stolen, rotated):
        assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": token})).status_code == 401


async def test_a_separate_login_is_its_own_family(client):
    # Revoking one compromised session must not sign the user out everywhere
    # else -- families are per-login for exactly this reason.
    await _register(client, "rotate-4@example.com", "Rotate House 4")

    session_a = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "rotate-4@example.com", "password": "a very good password"},
        )
    ).json()["refresh_token"]
    session_b = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "rotate-4@example.com", "password": "a very good password"},
        )
    ).json()["refresh_token"]

    # Burn session A by replaying it.
    await client.post("/api/v1/auth/refresh", json={"refresh_token": session_a})
    await client.post("/api/v1/auth/refresh", json={"refresh_token": session_a})
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": session_a})).status_code == 401

    # Session B is untouched.
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": session_b})).status_code == 200


async def test_legacy_token_without_jti_is_honoured_once_and_upgraded(client):
    """Deploying rotation must not log existing users out mid-session."""
    from app.core.security import create_refresh_token

    tokens = await _register(client, "rotate-5@example.com", "Rotate House 5")
    claims = __import__("jwt").decode(
        tokens["refresh_token"], options={"verify_signature": False}
    )
    legacy = create_refresh_token(
        user_id=__import__("uuid").UUID(claims["sub"]),
        household_id=__import__("uuid").UUID(claims["household_id"]),
    )

    upgraded = await client.post("/api/v1/auth/refresh", json={"refresh_token": legacy})
    assert upgraded.status_code == 200
    # ...and what comes back IS tracked, so it rotates from here on.
    new_token = upgraded.json()["refresh_token"]
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": new_token})).status_code == 200
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": new_token})).status_code == 401

# --- Reset tokens must not sit in logs on a working instance (review P1) ---
#
# Tested against the decision function rather than end-to-end: the
# instance-settings singleton is instance-wide mutable state seeded from env
# (and re-applied on every read when SMTP_FORCE_ENV is set), so a test that
# mutates it leaks into every other test in the session. That's the same
# isolation problem behind the pre-existing
# test_instance_admin_can_read_and_write_smtp_settings failure -- worth not
# adding two more instances of it.


class _Settings:
    def __init__(self, **kw):
        self.smtp_enabled = kw.get("smtp_enabled", True)
        self.smtp_host = kw.get("smtp_host", "smtp.example.com")
        self.smtp_from_address = kw.get("smtp_from_address", "noreply@example.com")


def test_smtp_can_deliver_requires_every_field():
    from app.api.v1.auth import smtp_can_deliver

    assert smtp_can_deliver(_Settings()) is True

    # Any one missing means email won't go out, so the link must fall back
    # to the log rather than vanishing entirely.
    assert smtp_can_deliver(None) is False
    assert smtp_can_deliver(_Settings(smtp_enabled=False)) is False
    assert smtp_can_deliver(_Settings(smtp_host="")) is False
    assert smtp_can_deliver(_Settings(smtp_from_address="")) is False


def test_smtp_can_deliver_matches_send_email_preconditions():
    """If these two ever drift, tokens either leak or go undeliverable."""
    import inspect

    from app.core.email import send_email

    source = inspect.getsource(send_email)
    for field in ("smtp_enabled", "smtp_host", "smtp_from_address"):
        assert field in source, (
            f"send_email no longer checks {field}; auth.smtp_can_deliver must be updated to match"
        )


async def test_reset_evicts_a_token_issued_in_the_same_second(client, db_session):
    """Regression: the whole flow completing inside one second must still evict.

    The first implementation compared a whole-second `iat` against a
    microsecond-precise cutoff and truncated the cutoff to match, which meant
    a token issued in the same second as the reset survived it. Easy to miss,
    because it only shows up when the reset happens fast -- which is exactly
    what an attacker's tooling would do, and what this test does.
    """
    email = "same-second@example.com"
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "a very good password",
            "display_name": "Same Second",
            "household_name": "Same Second House",
        },
    )
    stolen_headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    token = await _reset_token_for(db_session, email)
    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "a completely new password"},
    )
    assert reset.status_code == 200

    assert (await client.get("/api/v1/assets", headers=stolen_headers)).status_code == 401


# ===== self-service registration toggle =====


async def _close_signups(client, auth_headers) -> None:
    response = await client.put(
        "/api/v1/instance-settings",
        headers=auth_headers,
        json={"allow_self_registration": False},
    )
    assert response.status_code == 200
    assert response.json()["allow_self_registration"] is False


async def test_self_registration_open_by_default(client, auth_headers):
    response = await client.get("/api/v1/instance-settings", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["allow_self_registration"] is True


async def test_closing_signups_rejects_uninvited_registration(client, auth_headers):
    await _close_signups(client, auth_headers)

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "stranger@example.com",
            "password": "a very good password",
            "display_name": "Stranger",
            "household_name": "Stranger's House",
        },
    )
    assert response.status_code == 403


async def test_closing_signups_still_lets_an_invited_user_register(client, auth_headers):
    """The whole point of gating only the uninvited branch — an owner must not
    lose the ability to add people to their household when signups close."""
    invite = await client.post(
        "/api/v1/households/invites",
        headers=auth_headers,
        json={"invited_email": "invited@example.com"},
    )
    assert invite.status_code == 201
    token = invite.json()["token"]

    await _close_signups(client, auth_headers)

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "invited@example.com",
            "password": "a very good password",
            "display_name": "Invited",
            "invite_token": token,
        },
    )
    assert response.status_code == 201


async def test_setup_status_reports_the_registration_flag(client, auth_headers):
    assert (await client.get("/api/v1/auth/setup-status")).json()["allow_self_registration"] is True

    await _close_signups(client, auth_headers)

    body = (await client.get("/api/v1/auth/setup-status")).json()
    assert body["setup_complete"] is True
    assert body["allow_self_registration"] is False


async def test_closed_signups_never_block_the_first_ever_registration(client, db_session):
    """A restored-empty-database instance whose settings row says signups are
    closed must still allow the first-run admin account — otherwise there is
    nobody left who could reopen them."""
    db_session.add(InstanceSettings(allow_self_registration=False))
    await db_session.commit()

    status_body = (await client.get("/api/v1/auth/setup-status")).json()
    assert status_body["setup_complete"] is False
    assert status_body["allow_self_registration"] is True

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "first@example.com",
            "password": "a very good password",
            "display_name": "First",
            "household_name": "First House",
        },
    )
    assert response.status_code == 201
