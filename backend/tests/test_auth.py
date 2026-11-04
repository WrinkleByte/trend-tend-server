# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

async def test_register_creates_user_and_household(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bob@example.com",
            "password": "hunter2hunter2",
            "display_name": "Bob",
            "household_name": "Bob's Garage",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_register_duplicate_email_rejected(client, registered_user):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "another password",
            "display_name": "Alice 2",
            "household_name": "Another House",
        },
    )
    assert response.status_code == 409


async def test_login_with_correct_password(client, registered_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "correct horse battery staple"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_with_wrong_password_rejected(client, registered_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong password"},
    )
    assert response.status_code == 401


async def test_protected_endpoint_requires_auth(client):
    response = await client.get("/api/v1/households/me")
    assert response.status_code == 401


async def test_protected_endpoint_works_with_valid_token(client, auth_headers):
    response = await client.get("/api/v1/households/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Alice's House"


async def test_login_rate_limited_after_too_many_attempts(client, registered_user):
    # _auth_attempt_limiter allows 10 per 60s (auth.py) — the 11th request
    # from the same (synthetic, shared-across-this-test-client) IP should
    # be rejected before it even touches password verification, regardless
    # of whether the credentials themselves are right or wrong.
    for _ in range(10):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": "wrong password"},
        )
        assert response.status_code == 401

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong password"},
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


async def test_register_rate_limited_after_too_many_attempts(client):
    payload = {
        "email": "spammer@example.com",
        "password": "hunter2hunter2",
        "display_name": "Spammer",
        "household_name": "Spammer's House",
    }
    for _ in range(10):
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code in (201, 409)

    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


async def test_forgot_password_rate_limited_after_too_many_attempts(client, registered_user):
    # _password_reset_limiter allows 5 per 300s — stricter than login/register.
    for _ in range(5):
        response = await client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        assert response.status_code == 200

    response = await client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
    assert response.status_code == 429
    assert "Retry-After" in response.headers


async def test_refresh_rate_limited_after_too_many_attempts(client):
    # _refresh_limiter allows 30 per 60s (auth.py) -- higher than the others
    # since a legitimate client refreshes routinely, but still bounded: it's
    # unauthenticated and accepts a long-lived credential, so it needed its
    # own limiter rather than relying on the ones covering the other
    # auth endpoints (Vikunja #217).
    for _ in range(30):
        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"}
        )
        assert response.status_code == 401

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 429
    assert "Retry-After" in response.headers


async def test_reset_password_rate_limited_after_too_many_attempts(client):
    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": "not-a-real-token", "new_password": "irrelevant password"},
        )
        assert response.status_code == 400

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "irrelevant password"},
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers
