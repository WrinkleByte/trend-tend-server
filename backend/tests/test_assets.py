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
                "default_oil_capacity": "5 qt",
                "default_transmission_filter_part_number": "TF-45",
                "default_transmission_fluid_capacity": "9 qt",
                "default_differential_front_capacity": "1.5 qt",
                "default_differential_rear_capacity": "2 qt",
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
    assert details["default_oil_capacity"] == "5 qt"
    assert details["default_transmission_filter_part_number"] == "TF-45"
    assert details["default_transmission_fluid_capacity"] == "9 qt"
    assert details["default_differential_front_capacity"] == "1.5 qt"
    assert details["default_differential_rear_capacity"] == "2 qt"


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


# ===== owner_user_id: view filter, not access control =====


async def _member_of(client, auth_headers, email: str) -> str:
    """Adds a second person to the fixture household via the real invite flow
    and returns their user id."""
    invite = await client.post(
        "/api/v1/households/invites", headers=auth_headers, json={"invited_email": email}
    )
    assert invite.status_code == 201
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "a very good password",
            "display_name": email.split("@")[0],
            "invite_token": invite.json()["token"],
        },
    )
    assert register.status_code == 201
    members = await client.get("/api/v1/households/members", headers=auth_headers)
    return next(m["user_id"] for m in members.json() if m["email"] == email)


async def test_asset_owner_defaults_to_unassigned(client, auth_headers):
    response = await client.post(
        "/api/v1/assets", headers=auth_headers, json={"asset_type": "vehicle", "name": "Unclaimed"}
    )
    assert response.status_code == 201
    assert response.json()["owner_user_id"] is None


async def test_asset_can_be_assigned_to_a_household_member(client, auth_headers):
    other_id = await _member_of(client, auth_headers, "bob@example.com")

    created = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={"asset_type": "vehicle", "name": "Bob's Truck", "owner_user_id": other_id},
    )
    assert created.status_code == 201
    assert created.json()["owner_user_id"] == other_id


async def test_asset_owner_must_be_a_member_of_this_household(client, auth_headers):
    """A user id from another household is a cross-tenant reference, same class
    as Vikunja #32's asset_id/schedule_id — must be rejected, not stored."""
    outsider = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "outsider@example.com",
            "password": "a very good password",
            "display_name": "Outsider",
            "household_name": "Some Other House",
        },
    )
    outsider_headers = {"Authorization": f"Bearer {outsider.json()['access_token']}"}
    outsider_id = (await client.get("/api/v1/households/members", headers=outsider_headers)).json()[0]["user_id"]

    response = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={"asset_type": "vehicle", "name": "Hijacked", "owner_user_id": outsider_id},
    )
    assert response.status_code == 400


async def test_mine_only_filters_to_my_assets_plus_unassigned(client, auth_headers, registered_user):
    """The filter is a view preference: it keeps unowned assets (nobody should
    lose sight of an unclaimed asset) and drops only other people's."""
    other_id = await _member_of(client, auth_headers, "carol@example.com")
    me_id = (
        next(
            m["user_id"]
            for m in (await client.get("/api/v1/households/members", headers=auth_headers)).json()
            if m["email"] == "alice@example.com"
        )
    )

    for name, owner in (("Mine", me_id), ("Carol's", other_id), ("Unassigned", None)):
        body = {"asset_type": "vehicle", "name": name}
        if owner:
            body["owner_user_id"] = owner
        assert (await client.post("/api/v1/assets", headers=auth_headers, json=body)).status_code == 201

    unfiltered = await client.get("/api/v1/assets", headers=auth_headers)
    assert {a["name"] for a in unfiltered.json()} == {"Mine", "Carol's", "Unassigned"}

    filtered = await client.get("/api/v1/assets?mine_only=true", headers=auth_headers)
    assert {a["name"] for a in filtered.json()} == {"Mine", "Unassigned"}


async def test_other_members_can_still_read_an_owned_asset(client, auth_headers):
    """Ownership is explicitly NOT access control — confirm the filter didn't
    quietly become one."""
    invite = await client.post(
        "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "dave@example.com"}
    )
    dave = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "dave@example.com",
            "password": "a very good password",
            "display_name": "Dave",
            "invite_token": invite.json()["token"],
        },
    )
    dave_headers = {"Authorization": f"Bearer {dave.json()['access_token']}"}
    me_id = (
        next(
            m["user_id"]
            for m in (await client.get("/api/v1/households/members", headers=auth_headers)).json()
            if m["email"] == "alice@example.com"
        )
    )

    asset = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={"asset_type": "vehicle", "name": "Alice's Car", "owner_user_id": me_id},
    )
    asset_id = asset.json()["id"]

    assert (await client.get(f"/api/v1/assets/{asset_id}", headers=dave_headers)).status_code == 200
    assert "Alice's Car" in {a["name"] for a in (await client.get("/api/v1/assets", headers=dave_headers)).json()}


# ===== updated_by_user_id attribution =====


async def test_rest_writes_attribute_to_the_authenticated_user(client, auth_headers):
    me_id = (await client.get("/api/v1/households/members", headers=auth_headers)).json()[0]["user_id"]

    created = await client.post(
        "/api/v1/assets", headers=auth_headers, json={"asset_type": "vehicle", "name": "Attributed"}
    )
    assert created.json()["updated_by_user_id"] == me_id


async def test_attribution_follows_whoever_edited_last(client, auth_headers):
    invite = await client.post(
        "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "erin@example.com"}
    )
    erin = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "erin@example.com",
            "password": "a very good password",
            "display_name": "Erin",
            "invite_token": invite.json()["token"],
        },
    )
    erin_headers = {"Authorization": f"Bearer {erin.json()['access_token']}"}
    erin_id = next(
        m["user_id"]
        for m in (await client.get("/api/v1/households/members", headers=auth_headers)).json()
        if m["email"] == "erin@example.com"
    )

    asset = await client.post(
        "/api/v1/assets", headers=auth_headers, json={"asset_type": "vehicle", "name": "Shared Car"}
    )
    asset_id = asset.json()["id"]

    updated = await client.patch(
        f"/api/v1/assets/{asset_id}", headers=erin_headers, json={"name": "Shared Car (Erin)"}
    )
    assert updated.status_code == 200
    assert updated.json()["updated_by_user_id"] == erin_id
