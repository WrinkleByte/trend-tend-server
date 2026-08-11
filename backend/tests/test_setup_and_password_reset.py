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
        "/api/v1/auth/reset-password", json={"token": token.token, "new_password": "irrelevant"}
    )
    assert response.status_code == 400


async def test_reset_password_garbage_token_rejected(client):
    response = await client.post(
        "/api/v1/auth/reset-password", json={"token": "not-a-real-token", "new_password": "irrelevant"}
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
