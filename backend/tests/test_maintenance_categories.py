"""Maintenance categories API -- a household's remembered custom
service-type names (Vikunja #92 follow-up). Pure CRUD, no cross-table
references, so no verify_owned_reference coverage needed; cross-tenant
isolation is covered here directly rather than in test_household_isolation.py
since RLS + household_scoped_query are the only things enforcing it.
"""


async def test_create_list_get_update_delete_maintenance_category(client, auth_headers):
    created = await client.post(
        "/api/v1/maintenance-categories", headers=auth_headers, json={"name": "Wiper Blades"}
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Wiper Blades"
    assert body["version"] == 1
    category_id = body["id"]

    listed = await client.get("/api/v1/maintenance-categories", headers=auth_headers)
    assert listed.status_code == 200
    assert any(c["id"] == category_id for c in listed.json())

    fetched = await client.get(f"/api/v1/maintenance-categories/{category_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Wiper Blades"

    updated = await client.patch(
        f"/api/v1/maintenance-categories/{category_id}", headers=auth_headers, json={"name": "Wiper Blade Replacement"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Wiper Blade Replacement"
    assert updated.json()["version"] == 2

    deleted = await client.delete(f"/api/v1/maintenance-categories/{category_id}", headers=auth_headers)
    assert deleted.status_code == 204

    listed_after_delete = await client.get("/api/v1/maintenance-categories", headers=auth_headers)
    assert all(c["id"] != category_id for c in listed_after_delete.json())

    get_after_delete = await client.get(f"/api/v1/maintenance-categories/{category_id}", headers=auth_headers)
    assert get_after_delete.status_code == 404


async def test_unknown_maintenance_category_is_404(client, auth_headers):
    response = await client.get(
        "/api/v1/maintenance-categories/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404


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


async def test_household_cannot_see_or_touch_another_households_maintenance_category(client):
    user_a = await _register_and_login(client, "a-categories@example.com", "House A")
    user_b = await _register_and_login(client, "b-categories@example.com", "House B")
    headers_a = {"Authorization": f"Bearer {user_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['access_token']}"}

    created = await client.post(
        "/api/v1/maintenance-categories", headers=headers_a, json={"name": "House A's Custom Type"}
    )
    category_id = created.json()["id"]

    list_as_b = await client.get("/api/v1/maintenance-categories", headers=headers_b)
    assert all(c["id"] != category_id for c in list_as_b.json())

    get_as_b = await client.get(f"/api/v1/maintenance-categories/{category_id}", headers=headers_b)
    assert get_as_b.status_code == 404

    update_as_b = await client.patch(
        f"/api/v1/maintenance-categories/{category_id}", headers=headers_b, json={"name": "Hijacked"}
    )
    assert update_as_b.status_code == 404

    delete_as_b = await client.delete(f"/api/v1/maintenance-categories/{category_id}", headers=headers_b)
    assert delete_as_b.status_code == 404

    still_there = await client.get(f"/api/v1/maintenance-categories/{category_id}", headers=headers_a)
    assert still_there.status_code == 200
    assert still_there.json()["name"] == "House A's Custom Type"
