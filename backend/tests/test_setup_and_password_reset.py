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


async def test_setup_status_false_before_any_user_exists(client):
    response = await client.get("/api/v1/auth/setup-status")
    assert response.status_code == 200
    assert response.json() == {"setup_complete": False}


async def test_setup_status_true_after_first_user_registers(client):
    await _register(client, "first@example.com", "First House")
    response = await client.get("/api/v1/auth/setup-status")
    assert response.json() == {"setup_complete": True}


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
