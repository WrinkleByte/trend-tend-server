# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

async def _create_vehicle(client, auth_headers) -> str:
    response = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={"asset_type": "vehicle", "name": "Family Minivan", "vehicle_details": {"current_mileage": 41500}},
    )
    return response.json()["id"]


async def test_create_and_get_trip_log(client, auth_headers):
    asset_id = await _create_vehicle(client, auth_headers)

    response = await client.post(
        "/api/v1/trip-logs",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-01-15T09:00:00Z",
            "purpose": "business",
            "start_odometer": "41500.0",
            "end_odometer": "41542.0",
            "distance": "42.0",
        },
    )
    assert response.status_code == 201
    trip_log = response.json()
    assert trip_log["asset_id"] == asset_id
    assert trip_log["purpose"] == "business"
    assert trip_log["distance"] == "42.0"
    assert trip_log["version"] == 1

    get_response = await client.get(f"/api/v1/trip-logs/{trip_log['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["end_odometer"] == "41542.0"


async def test_create_trip_log_with_custom_purpose(client, auth_headers):
    asset_id = await _create_vehicle(client, auth_headers)

    response = await client.post(
        "/api/v1/trip-logs",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-01-15T09:00:00Z",
            "purpose": "other",
            "custom_purpose": "Airport pickup",
            "end_odometer": "41542.0",
            "distance": "42.0",
        },
    )
    assert response.status_code == 201
    trip_log = response.json()
    assert trip_log["purpose"] == "other"
    assert trip_log["custom_purpose"] == "Airport pickup"
    assert trip_log["start_odometer"] is None


async def test_list_trip_logs_filtered_by_asset(client, auth_headers):
    asset_id = await _create_vehicle(client, auth_headers)
    other_asset_id = await _create_vehicle(client, auth_headers)

    await client.post(
        "/api/v1/trip-logs",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-01-01T00:00:00Z",
            "purpose": "commute",
            "end_odometer": "100",
            "distance": "10",
        },
    )
    await client.post(
        "/api/v1/trip-logs",
        headers=auth_headers,
        json={
            "asset_id": other_asset_id,
            "performed_at": "2026-01-02T00:00:00Z",
            "purpose": "personal",
            "end_odometer": "50",
            "distance": "5",
        },
    )

    response = await client.get("/api/v1/trip-logs", headers=auth_headers, params={"asset_id": asset_id})
    assert response.status_code == 200
    logs = response.json()
    assert len(logs) == 1
    assert logs[0]["asset_id"] == asset_id


async def test_update_trip_log_bumps_version(client, auth_headers):
    asset_id = await _create_vehicle(client, auth_headers)
    create = await client.post(
        "/api/v1/trip-logs",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-01-01T00:00:00Z",
            "purpose": "business",
            "end_odometer": "100",
            "distance": "10",
        },
    )
    trip_log_id = create.json()["id"]

    update = await client.patch(
        f"/api/v1/trip-logs/{trip_log_id}",
        headers=auth_headers,
        json={"notes": "Client meeting downtown", "distance": "12.5"},
    )
    assert update.status_code == 200
    body = update.json()
    assert body["notes"] == "Client meeting downtown"
    assert body["distance"] == "12.5"
    assert body["version"] == 2


async def test_delete_trip_log_is_soft_delete(client, auth_headers):
    asset_id = await _create_vehicle(client, auth_headers)
    create = await client.post(
        "/api/v1/trip-logs",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-01-01T00:00:00Z",
            "purpose": "medical",
            "end_odometer": "100",
            "distance": "10",
        },
    )
    trip_log_id = create.json()["id"]

    delete = await client.delete(f"/api/v1/trip-logs/{trip_log_id}", headers=auth_headers)
    assert delete.status_code == 204

    get_after_delete = await client.get(f"/api/v1/trip-logs/{trip_log_id}", headers=auth_headers)
    assert get_after_delete.status_code == 404

    list_response = await client.get("/api/v1/trip-logs", headers=auth_headers)
    assert trip_log_id not in [t["id"] for t in list_response.json()]


async def test_trip_log_household_isolation(client, auth_headers):
    asset_id = await _create_vehicle(client, auth_headers)
    await client.post(
        "/api/v1/trip-logs",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-01-01T00:00:00Z",
            "purpose": "charity",
            "end_odometer": "100",
            "distance": "10",
        },
    )

    other_user = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "othertrip@example.com",
            "password": "a very good password",
            "display_name": "Other",
            "household_name": "Other House",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_user.json()['access_token']}"}

    response = await client.get("/api/v1/trip-logs", headers=other_headers)
    assert response.json() == []
