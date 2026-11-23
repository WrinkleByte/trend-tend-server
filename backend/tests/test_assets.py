# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

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


async def test_service_defaults_brands_arrive_through_the_vehicle_shape(client, auth_headers):
    """The REST half of the same contract the phones use.

    Brands were never vehicle_details columns, but the shipped mobile build sends them there,
    and a key the schema does not declare is gone before any handler sees it -- while the
    request still returns 201. Both directions are asserted because both are needed: written
    into service_defaults, and readable from vehicle_details by a client that has never heard
    of the new table.
    """
    create = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={
            "asset_type": "vehicle",
            "name": "Pickup",
            "vehicle_details": {
                "make": "Ford",
                "default_oil_viscosity": "5W-30",
                "default_motor_oil_brand": "Valvoline",
                "default_oil_filter_brand": "Fram",
            },
        },
    )
    assert create.status_code == 201, create.text
    asset_id = create.json()["id"]
    body = create.json()
    assert body["vehicle_details"]["default_motor_oil_brand"] == "Valvoline"
    assert body["vehicle_details"]["default_oil_filter_brand"] == "Fram"
    assert body["service_defaults"]["default_motor_oil_brand"] == "Valvoline"
    assert body["service_defaults"]["default_oil_viscosity"] == "5W-30"

    # A later edit that never mentions brands must not clear them -- the field set the client
    # sent is the only thing the server is allowed to write.
    patch = await client.patch(
        f"/api/v1/assets/{asset_id}",
        headers=auth_headers,
        json={"service_defaults": {"default_oil_viscosity": "0W-20"}},
    )
    assert patch.status_code == 200, patch.text
    stored = (await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)).json()
    assert stored["service_defaults"]["default_oil_viscosity"] == "0W-20"
    assert stored["service_defaults"]["default_motor_oil_brand"] == "Valvoline"
    assert stored["vehicle_details"]["default_oil_filter_brand"] == "Fram"


async def test_service_defaults_are_not_vehicle_only(client, auth_headers):
    """The table is keyed by asset, not by asset type: an equipment asset can hold the specs
    its category list offers, and no vehicle_details row is needed for it."""
    create = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={
            "asset_type": "equipment",
            "name": "Tractor",
            "equipment_details": {"manufacturer": "Kubota"},
            "service_defaults": {
                "default_oil_viscosity": "10W-30",
                "default_hydraulic_fluid_type": "ISO 46",
                "default_hvac_filter_size": "20x25x1",
            },
        },
    )
    assert create.status_code == 201, create.text
    saved = create.json()["service_defaults"]
    assert saved["default_oil_viscosity"] == "10W-30"
    assert saved["default_hydraulic_fluid_type"] == "ISO 46"
    assert saved["default_hvac_filter_size"] == "20x25x1"


async def test_valuable_assets_get_no_service_defaults_row(client, auth_headers):
    """ServiceDefaultsIn promises "valuable assets get no row", because their categories
    (repair, replacement, appraisal) are not spec-driven: nothing a default could prefill,
    nothing a cart would search for. The write path has to keep that promise rather than
    document it -- it used to store whatever arrived, which left a spec row hanging off an
    asset that can never use it, reported back to the client as if it were saved.

    Dropping the intent is the safe half; removing a row an earlier build already wrote is
    the repair, so a valuable asset that picked up specs by accident stops reporting them.
    """
    create = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={
            "asset_type": "valuable",
            "name": "Upright Piano",
            "valuable_details": {"manufacturer": "Steinway"},
            "service_defaults": {"default_oil_viscosity": "should-not-land"},
        },
    )
    assert create.status_code == 201, create.text
    asset = create.json()
    assert asset["service_defaults"] is None

    patch = await client.patch(
        f"/api/v1/assets/{asset['id']}",
        headers=auth_headers,
        json={"service_defaults": {"default_oil_viscosity": "still-should-not-land"}},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["service_defaults"] is None

    stored = await client.get(f"/api/v1/assets/{asset['id']}", headers=auth_headers)
    assert stored.json()["service_defaults"] is None


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


async def test_sale_price_set_and_cleared_through_rest(client, auth_headers):
    created = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={"asset_type": "vehicle", "name": "Wagon", "purchase_cost": "20000.00"},
    )
    asset_id = created.json()["id"]
    assert created.json()["sale_price"] is None

    sold = await client.patch(
        f"/api/v1/assets/{asset_id}",
        headers=auth_headers,
        json={"status": "archived", "sale_price": "8500.00", "sale_date": "2026-10-01"},
    )
    assert sold.status_code == 200
    assert sold.json()["sale_price"] == "8500.00"
    assert sold.json()["sale_date"] == "2026-10-01"

    # Leaving the keys out leaves the sale alone...
    renamed = await client.patch(f"/api/v1/assets/{asset_id}", headers=auth_headers, json={"name": "Old Wagon"})
    assert renamed.json()["sale_price"] == "8500.00"

    # ...and an explicit null clears it.
    cleared = await client.patch(
        f"/api/v1/assets/{asset_id}",
        headers=auth_headers,
        json={"status": "active", "sale_price": None, "sale_date": None},
    )
    assert cleared.json()["sale_price"] is None
    assert cleared.json()["sale_date"] is None


async def test_negative_sale_price_is_rejected(client, auth_headers):
    created = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={"asset_type": "vehicle", "name": "Wagon", "status": "archived", "sale_price": "-5.00"},
    )
    assert created.status_code == 422

    created = await client.post("/api/v1/assets", headers=auth_headers, json={"asset_type": "vehicle", "name": "Wagon"})
    asset_id = created.json()["id"]
    patched = await client.patch(f"/api/v1/assets/{asset_id}", headers=auth_headers, json={"sale_price": "-5.00"})
    assert patched.status_code == 422
    # Zero is a real answer (scrapped for nothing), not an error.
    patched = await client.patch(f"/api/v1/assets/{asset_id}", headers=auth_headers, json={"sale_price": "0"})
    assert patched.status_code == 200
    assert patched.json()["sale_price"] == "0.00"


async def test_equipment_fill_up_unit_over_rest(client, auth_headers):
    """The web app sets it; a REST caller that doesn't send it keeps the stored choice."""
    create = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={"asset_type": "equipment", "name": "ATV", "equipment_details": {"fuel_reading_unit": "odometer"}},
    )
    assert create.status_code == 201
    asset_id = create.json()["id"]
    assert create.json()["equipment_details"]["fuel_reading_unit"] == "odometer"

    unaware = await client.patch(
        f"/api/v1/assets/{asset_id}", headers=auth_headers, json={"equipment_details": {"manufacturer": "Polaris"}}
    )
    assert unaware.status_code == 200
    assert unaware.json()["equipment_details"]["manufacturer"] == "Polaris"
    assert unaware.json()["equipment_details"]["fuel_reading_unit"] == "odometer"

    back = await client.patch(
        f"/api/v1/assets/{asset_id}", headers=auth_headers, json={"equipment_details": {"fuel_reading_unit": "hours"}}
    )
    assert back.json()["equipment_details"]["fuel_reading_unit"] == "hours"
