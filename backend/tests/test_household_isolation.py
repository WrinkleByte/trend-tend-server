async def _register_and_login(client, email: str, household_name: str) -> dict:
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


async def test_user_cannot_see_another_households_assets(client):
    user_a = await _register_and_login(client, "a@example.com", "House A")
    user_b = await _register_and_login(client, "b@example.com", "House B")
    headers_a = {"Authorization": f"Bearer {user_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['access_token']}"}

    create = await client.post(
        "/api/v1/assets", headers=headers_a, json={"asset_type": "equipment", "name": "House A's Mower"}
    )
    asset_id = create.json()["id"]

    list_as_b = await client.get("/api/v1/assets", headers=headers_b)
    assert list_as_b.json() == []

    get_as_b = await client.get(f"/api/v1/assets/{asset_id}", headers=headers_b)
    assert get_as_b.status_code == 404
