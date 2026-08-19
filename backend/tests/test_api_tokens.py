async def test_create_api_token_returns_raw_token_once(client, auth_headers):
    response = await client.post("/api/v1/api-tokens", headers=auth_headers, json={"name": "iPhone"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "iPhone"
    assert body["token"].startswith("mnt_live_")

    list_response = await client.get("/api/v1/api-tokens", headers=auth_headers)
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert "token" not in listed[0]
    assert listed[0]["id"] == body["id"]


async def test_created_api_token_authenticates_requests(client, auth_headers):
    create = await client.post("/api/v1/api-tokens", headers=auth_headers, json={"name": "iPhone"})
    raw_token = create.json()["token"]

    response = await client.get("/api/v1/assets", headers={"Authorization": f"Bearer {raw_token}"})
    assert response.status_code == 200


async def test_revoked_api_token_is_rejected(client, auth_headers):
    create = await client.post("/api/v1/api-tokens", headers=auth_headers, json={"name": "iPhone"})
    token_id = create.json()["id"]
    raw_token = create.json()["token"]

    revoke = await client.delete(f"/api/v1/api-tokens/{token_id}", headers=auth_headers)
    assert revoke.status_code == 204

    response = await client.get("/api/v1/assets", headers={"Authorization": f"Bearer {raw_token}"})
    assert response.status_code == 401

    list_response = await client.get("/api/v1/api-tokens", headers=auth_headers)
    assert list_response.json()[0]["revoked_at"] is not None


async def test_cannot_revoke_another_users_api_token(client, auth_headers):
    create = await client.post("/api/v1/api-tokens", headers=auth_headers, json={"name": "iPhone"})
    token_id = create.json()["id"]

    other_user = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "other@example.com",
            "password": "a very good password",
            "display_name": "Other",
            "household_name": "Other House",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_user.json()['access_token']}"}

    response = await client.delete(f"/api/v1/api-tokens/{token_id}", headers=other_headers)
    assert response.status_code == 404


# --- Deleting a revoked token (Vikunja #26) ---


async def test_revoked_token_can_be_deleted_permanently(client, auth_headers):
    created = await client.post(
        "/api/v1/api-tokens", headers=auth_headers, json={"name": "Old laptop"}
    )
    token_id = created.json()["id"]

    assert (await client.delete(f"/api/v1/api-tokens/{token_id}", headers=auth_headers)).status_code == 204
    assert (
        await client.delete(f"/api/v1/api-tokens/{token_id}/permanently", headers=auth_headers)
    ).status_code == 204

    listing = await client.get("/api/v1/api-tokens", headers=auth_headers)
    assert token_id not in [t["id"] for t in listing.json()]


async def test_a_live_token_cannot_be_deleted_without_revoking_first(client, auth_headers):
    # Deleting a live token in one step would destroy the audit trail of a
    # credential still in use, and skip the moment someone might notice they
    # picked the wrong one.
    created = await client.post(
        "/api/v1/api-tokens", headers=auth_headers, json={"name": "Still in use"}
    )
    token_id = created.json()["id"]

    response = await client.delete(f"/api/v1/api-tokens/{token_id}/permanently", headers=auth_headers)
    assert response.status_code == 409

    listing = await client.get("/api/v1/api-tokens", headers=auth_headers)
    assert token_id in [t["id"] for t in listing.json()]
