# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

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


def _headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_owner_can_set_household_settings_defaults(client, auth_headers):
    response = await client.patch(
        "/api/v1/households/me/settings",
        headers=auth_headers,
        json={"car_display_theme": "greenVFD", "stylized_plate_enabled": True, "unit_system": "metric"},
    )
    assert response.status_code == 200
    assert response.json()["settings"] == {
        "car_display_theme": "greenVFD",
        "stylized_plate_enabled": True,
        "unit_system": "metric",
    }

    get_response = await client.get("/api/v1/households/me", headers=auth_headers)
    assert get_response.json()["settings"]["car_display_theme"] == "greenVFD"


async def test_household_settings_update_merges_not_replaces(client, auth_headers):
    await client.patch(
        "/api/v1/households/me/settings",
        headers=auth_headers,
        json={"car_display_theme": "greenVFD", "unit_system": "metric"},
    )

    response = await client.patch(
        "/api/v1/households/me/settings",
        headers=auth_headers,
        json={"stylized_plate_enabled": False},
    )
    assert response.status_code == 200
    # unit_system/car_display_theme from the first PATCH must survive a
    # second PATCH that doesn't mention them -- merge, not replace.
    assert response.json()["settings"] == {
        "car_display_theme": "greenVFD",
        "unit_system": "metric",
        "stylized_plate_enabled": False,
    }


async def test_non_owner_cannot_set_household_settings(client, auth_headers):
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "member@example.com"}
        )
    ).json()

    member_tokens = await _register(client, "member@example.com", "irrelevant")
    accept = await client.post(
        "/api/v1/households/invites/accept",
        headers=_headers(member_tokens),
        json={"token": invite["token"]},
    )
    assert accept.status_code == 200
    member_headers = _headers(accept.json())

    response = await client.patch(
        "/api/v1/households/me/settings",
        headers=member_headers,
        json={"car_display_theme": "redAlert"},
    )
    assert response.status_code == 403

    # Owner's household settings are untouched by the rejected attempt.
    get_response = await client.get("/api/v1/households/me", headers=auth_headers)
    assert get_response.json()["settings"] == {}
