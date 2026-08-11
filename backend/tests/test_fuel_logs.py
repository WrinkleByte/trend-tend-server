async def _create_vehicle(client, auth_headers) -> str:
    response = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={"asset_type": "vehicle", "name": "Family Minivan", "vehicle_details": {"current_mileage": 41500}},
    )
    return response.json()["id"]


async def test_create_and_get_fuel_log(client, auth_headers):
    asset_id = await _create_vehicle(client, auth_headers)

    response = await client.post(
        "/api/v1/fuel-logs",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-01-15",
            "odometer_reading": 41800,
            "gallons": "12.5",
            "cost_per_gallon": "3.459",
            "total_cost": "43.24",
        },
    )
    assert response.status_code == 201
    fuel_log = response.json()
    assert fuel_log["asset_id"] == asset_id
    assert fuel_log["gallons"] == "12.500"
    assert fuel_log["is_fill_up"] is True
    assert fuel_log["version"] == 1

    get_response = await client.get(f"/api/v1/fuel-logs/{fuel_log['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["cost_per_gallon"] == "3.459"


async def test_list_fuel_logs_filtered_by_asset(client, auth_headers):
    asset_id = await _create_vehicle(client, auth_headers)
    other_asset_id = await _create_vehicle(client, auth_headers)

    await client.post(
        "/api/v1/fuel-logs",
        headers=auth_headers,
        json={"asset_id": asset_id, "performed_at": "2026-01-01", "gallons": "10"},
    )
    await client.post(
        "/api/v1/fuel-logs",
        headers=auth_headers,
        json={"asset_id": other_asset_id, "performed_at": "2026-01-02", "gallons": "8"},
    )

    response = await client.get("/api/v1/fuel-logs", headers=auth_headers, params={"asset_id": asset_id})
    assert response.status_code == 200
    logs = response.json()
    assert len(logs) == 1
    assert logs[0]["asset_id"] == asset_id


async def test_update_fuel_log_bumps_version(client, auth_headers):
    asset_id = await _create_vehicle(client, auth_headers)
    create = await client.post(
        "/api/v1/fuel-logs",
        headers=auth_headers,
        json={"asset_id": asset_id, "performed_at": "2026-01-01", "gallons": "10", "is_fill_up": False},
    )
    fuel_log_id = create.json()["id"]

    update = await client.patch(
        f"/api/v1/fuel-logs/{fuel_log_id}", headers=auth_headers, json={"is_fill_up": True, "mpg": "28.4"}
    )
    assert update.status_code == 200
    body = update.json()
    assert body["is_fill_up"] is True
    assert body["mpg"] == "28.40"
    assert body["version"] == 2


async def test_delete_fuel_log_is_soft_delete(client, auth_headers):
    asset_id = await _create_vehicle(client, auth_headers)
    create = await client.post(
        "/api/v1/fuel-logs",
        headers=auth_headers,
        json={"asset_id": asset_id, "performed_at": "2026-01-01", "gallons": "10"},
    )
    fuel_log_id = create.json()["id"]

    delete = await client.delete(f"/api/v1/fuel-logs/{fuel_log_id}", headers=auth_headers)
    assert delete.status_code == 204

    get_after_delete = await client.get(f"/api/v1/fuel-logs/{fuel_log_id}", headers=auth_headers)
    assert get_after_delete.status_code == 404

    list_response = await client.get("/api/v1/fuel-logs", headers=auth_headers)
    assert fuel_log_id not in [f["id"] for f in list_response.json()]


async def test_fuel_log_household_isolation(client, auth_headers):
    asset_id = await _create_vehicle(client, auth_headers)
    await client.post(
        "/api/v1/fuel-logs",
        headers=auth_headers,
        json={"asset_id": asset_id, "performed_at": "2026-01-01", "gallons": "10"},
    )

    other_user = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "otherfuel@example.com",
            "password": "a very good password",
            "display_name": "Other",
            "household_name": "Other House",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_user.json()['access_token']}"}

    response = await client.get("/api/v1/fuel-logs", headers=other_headers)
    assert response.json() == []
