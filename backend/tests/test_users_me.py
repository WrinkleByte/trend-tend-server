# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""GET/PATCH /users/me: changing your own display name (capability
profile_display_name)."""


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_get_me_describes_the_signed_in_user(client, auth_headers):
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Alice"
    assert body["has_login"] is True
    assert body["email"]


async def test_change_own_display_name_shows_everywhere(client, auth_headers):
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"display_name": "  Alice Smith  "},
    )
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "Alice Smith"

    members = (
        await client.get("/api/v1/households/members", headers=auth_headers)
    ).json()
    assert [m["display_name"] for m in members] == ["Alice Smith"]


async def test_blank_or_too_long_name_is_refused(client, auth_headers):
    for name in ["", "   ", "x" * 201]:
        response = await client.patch(
            "/api/v1/users/me", headers=auth_headers, json={"display_name": name}
        )
        assert response.status_code == 422, name
    assert (await client.get("/api/v1/users/me", headers=auth_headers)).json()[
        "display_name"
    ] == "Alice"


async def test_empty_update_changes_nothing(client, auth_headers):
    response = await client.patch("/api/v1/users/me", headers=auth_headers, json={})
    assert response.status_code == 200
    assert response.json()["display_name"] == "Alice"


async def test_needs_sign_in(client):
    assert (await client.get("/api/v1/users/me")).status_code == 401
    assert (
        await client.patch("/api/v1/users/me", json={"display_name": "X"})
    ).status_code == 401


async def test_device_key_renames_its_own_member_not_the_issuer(client, auth_headers):
    kate = (
        await client.post(
            "/api/v1/households/members",
            headers=auth_headers,
            json={"display_name": "Kate"},
        )
    ).json()
    key = (
        await client.post(
            f"/api/v1/households/members/{kate['user_id']}/api-tokens",
            headers=auth_headers,
            json={"name": "Kate's phone"},
        )
    ).json()

    response = await client.patch(
        "/api/v1/users/me",
        headers=_headers(key["token"]),
        json={"display_name": "Katie"},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == kate["user_id"]
    assert response.json()["has_login"] is False

    names = {
        m["display_name"]
        for m in (
            await client.get("/api/v1/households/members", headers=auth_headers)
        ).json()
    }
    assert names == {"Alice", "Katie"}
