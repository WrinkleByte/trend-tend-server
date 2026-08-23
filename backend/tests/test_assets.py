async def test_create_and_get_vehicle_asset(client, auth_headers):
    response = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={
            "asset_type": "vehicle",
            "name": "Family Minivan",
            "vehicle_details": {"make": "Honda", "model": "Odyssey", "year": 2019, "current_mileage": 42000},
        },
    )
    assert response.status_code == 201
    asset = response.json()
    assert asset["name"] == "Family Minivan"
    assert asset["vehicle_details"]["make"] == "Honda"
    assert asset["version"] == 1

    get_response = await client.get(f"/api/v1/assets/{asset['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["vehicle_details"]["model"] == "Odyssey"


async def test_vehicle_service_defaults_round_trip(client, auth_headers):
    response = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={
            "asset_type": "vehicle",
            "name": "Family Minivan",
            "vehicle_details": {
                "make": "Honda",
                "model": "Odyssey",
                "default_oil_viscosity": "5W-30",
                "default_oil_formulation": "full_synthetic",
                "default_oil_meets_dexos": False,
                "default_oil_filter_part_number": "PF-63",
                "default_air_filter_part_number": "AF-112",
                "default_transmission_fluid_type": "Honda ATF-Z1",
                "default_coolant_type": "Honda Type 2",
                "default_differential_front_fluid_type": "75W-90",
                "default_differential_rear_fluid_type": "75W-90",
            },
        },
    )
    assert response.status_code == 201, response.text
    details = response.json()["vehicle_details"]
    assert details["default_oil_viscosity"] == "5W-30"
    assert details["default_oil_formulation"] == "full_synthetic"
    assert details["default_oil_meets_dexos"] is False
    assert details["default_oil_filter_part_number"] == "PF-63"
    assert details["default_air_filter_part_number"] == "AF-112"
    assert details["default_transmission_fluid_type"] == "Honda ATF-Z1"
    assert details["default_coolant_type"] == "Honda Type 2"
    assert details["default_differential_front_fluid_type"] == "75W-90"
    assert details["default_differential_rear_fluid_type"] == "75W-90"


async def test_create_equipment_asset(client, auth_headers):
    response = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={
            "asset_type": "equipment",
            "name": "Snow Blower",
            "equipment_details": {"manufacturer": "Toro", "model_number": "38381"},
        },
    )
    assert response.status_code == 201
    assert response.json()["equipment_details"]["manufacturer"] == "Toro"


async def test_update_asset_bumps_version(client, auth_headers):
    create = await client.post(
        "/api/v1/assets", headers=auth_headers, json={"asset_type": "equipment", "name": "Lawn Mower"}
    )
    asset_id = create.json()["id"]

    update = await client.patch(
        f"/api/v1/assets/{asset_id}", headers=auth_headers, json={"name": "Riding Lawn Mower"}
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Riding Lawn Mower"
    assert update.json()["version"] == 2


async def test_delete_asset_is_soft_delete(client, auth_headers):
    create = await client.post(
        "/api/v1/assets", headers=auth_headers, json={"asset_type": "equipment", "name": "Leaf Blower"}
    )
    asset_id = create.json()["id"]

    delete = await client.delete(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert delete.status_code == 204

    get_after_delete = await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert get_after_delete.status_code == 404

    list_response = await client.get("/api/v1/assets", headers=auth_headers)
    assert asset_id not in [a["id"] for a in list_response.json()]


async def test_list_assets_only_returns_own_household(client, auth_headers):
    await client.post("/api/v1/assets", headers=auth_headers, json={"asset_type": "equipment", "name": "Generator"})
    response = await client.get("/api/v1/assets", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
