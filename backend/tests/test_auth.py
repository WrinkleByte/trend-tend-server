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
