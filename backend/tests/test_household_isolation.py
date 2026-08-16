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


# --- Cross-household foreign-key injection (Vikunja #32) ---
#
# create_fuel_log/create_trip_log/create_record/create_schedule and the
# generic sync push handler all spread a client-supplied asset_id (and, for
# maintenance records, schedule_id) directly onto a new row with
# household_id = the CALLER's own -- nothing verified those referenced ids
# actually belonged to the caller before this fix. Household B couldn't
# read Household A's data through this (every list/get is still scoped to
# the caller's own household_id), but B *could* attach a row to A's asset,
# a cross-tenant write with no ownership check at all. verify_owned_reference
# (app/api/deps.py) closes this for both the REST create endpoints and
# sync's _apply_change (create AND update-existing-row paths).


async def test_cannot_create_fuel_log_against_another_households_asset(client):
    owner = await _register_and_login(client, "owner-fuel@example.com", "House Owner")
    attacker = await _register_and_login(client, "attacker-fuel@example.com", "House Attacker")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    attacker_headers = {"Authorization": f"Bearer {attacker['access_token']}"}

    victim_asset = await client.post(
        "/api/v1/assets", headers=owner_headers, json={"asset_type": "vehicle", "name": "Victim Truck"}
    )
    victim_asset_id = victim_asset.json()["id"]

    response = await client.post(
        "/api/v1/fuel-logs",
        headers=attacker_headers,
        json={"asset_id": victim_asset_id, "performed_at": "2026-01-01", "gallons": "10"},
    )
    assert response.status_code == 404


async def test_cannot_create_trip_log_against_another_households_asset(client):
    owner = await _register_and_login(client, "owner-trip@example.com", "House Owner")
    attacker = await _register_and_login(client, "attacker-trip@example.com", "House Attacker")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    attacker_headers = {"Authorization": f"Bearer {attacker['access_token']}"}

    victim_asset = await client.post(
        "/api/v1/assets", headers=owner_headers, json={"asset_type": "vehicle", "name": "Victim Truck"}
    )
    victim_asset_id = victim_asset.json()["id"]

    response = await client.post(
        "/api/v1/trip-logs",
        headers=attacker_headers,
        json={
            "asset_id": victim_asset_id,
            "performed_at": "2026-01-01T09:00:00Z",
            "purpose": "business",
            "end_odometer": "100.0",
            "distance": "10.0",
        },
    )
    assert response.status_code == 404


async def test_cannot_create_maintenance_record_against_another_households_asset(client):
    owner = await _register_and_login(client, "owner-record@example.com", "House Owner")
    attacker = await _register_and_login(client, "attacker-record@example.com", "House Attacker")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    attacker_headers = {"Authorization": f"Bearer {attacker['access_token']}"}

    victim_asset = await client.post(
        "/api/v1/assets", headers=owner_headers, json={"asset_type": "equipment", "name": "Victim Mower"}
    )
    victim_asset_id = victim_asset.json()["id"]

    response = await client.post(
        "/api/v1/maintenance-records",
        headers=attacker_headers,
        json={"asset_id": victim_asset_id, "performed_at": "2026-01-01", "category": "repair"},
    )
    assert response.status_code == 404


async def test_cannot_create_maintenance_record_with_another_households_schedule_id(client):
    owner = await _register_and_login(client, "owner-schedule@example.com", "House Owner")
    attacker = await _register_and_login(client, "attacker-schedule@example.com", "House Attacker")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    attacker_headers = {"Authorization": f"Bearer {attacker['access_token']}"}

    victim_asset = await client.post(
        "/api/v1/assets", headers=owner_headers, json={"asset_type": "equipment", "name": "Victim Mower"}
    )
    victim_asset_id = victim_asset.json()["id"]
    victim_schedule = await client.post(
        "/api/v1/maintenance-schedules",
        headers=owner_headers,
        json={"asset_id": victim_asset_id, "name": "Oil change", "interval_type": "time", "interval_days": 90},
    )
    victim_schedule_id = victim_schedule.json()["id"]

    attacker_asset = await client.post(
        "/api/v1/assets", headers=attacker_headers, json={"asset_type": "equipment", "name": "Attacker Mower"}
    )
    attacker_asset_id = attacker_asset.json()["id"]

    response = await client.post(
        "/api/v1/maintenance-records",
        headers=attacker_headers,
        json={
            "asset_id": attacker_asset_id,
            "performed_at": "2026-01-01",
            "category": "repair",
            "schedule_id": victim_schedule_id,
        },
    )
    assert response.status_code == 404


async def test_cannot_create_maintenance_schedule_against_another_households_asset(client):
    owner = await _register_and_login(client, "owner-msched@example.com", "House Owner")
    attacker = await _register_and_login(client, "attacker-msched@example.com", "House Attacker")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    attacker_headers = {"Authorization": f"Bearer {attacker['access_token']}"}

    victim_asset = await client.post(
        "/api/v1/assets", headers=owner_headers, json={"asset_type": "vehicle", "name": "Victim Truck"}
    )
    victim_asset_id = victim_asset.json()["id"]

    response = await client.post(
        "/api/v1/maintenance-schedules",
        headers=attacker_headers,
        json={"asset_id": victim_asset_id, "name": "Oil change", "interval_type": "time", "interval_days": 90},
    )
    assert response.status_code == 404


async def test_sync_push_cannot_create_fuel_log_against_another_households_asset(client):
    owner = await _register_and_login(client, "owner-syncpush@example.com", "House Owner")
    attacker = await _register_and_login(client, "attacker-syncpush@example.com", "House Attacker")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    attacker_headers = {"Authorization": f"Bearer {attacker['access_token']}"}

    victim_asset = await client.post(
        "/api/v1/assets", headers=owner_headers, json={"asset_type": "vehicle", "name": "Victim Truck"}
    )
    victim_asset_id = victim_asset.json()["id"]

    device = await client.post(
        "/api/v1/sync/devices", headers=attacker_headers, json={"platform": "ios", "device_name": "Attacker Phone"}
    )
    device_id = device.json()["id"]

    push = await client.post(
        "/api/v1/sync/push",
        headers=attacker_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "fuel_log",
                    "id": "11111111-1111-1111-1111-111111111111",
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"asset_id": victim_asset_id, "performed_at": "2026-01-01", "gallons": "10"},
                }
            ],
        },
    )
    result = push.json()["results"][0]
    assert result["status"] == "rejected"
    assert result["reason"] == "invalid_reference"


async def test_sync_push_cannot_reassign_an_owned_fuel_log_to_another_households_asset(client):
    """The more dangerous half of this bug: not just creating a fresh
    cross-tenant reference, but taking an already-existing fuel log that
    genuinely belongs to the attacker's own household and, via sync's
    full-row-replace push semantics, relinking it to point at a victim
    household's asset instead."""
    owner = await _register_and_login(client, "owner-reassign@example.com", "House Owner")
    attacker = await _register_and_login(client, "attacker-reassign@example.com", "House Attacker")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    attacker_headers = {"Authorization": f"Bearer {attacker['access_token']}"}

    victim_asset = await client.post(
        "/api/v1/assets", headers=owner_headers, json={"asset_type": "vehicle", "name": "Victim Truck"}
    )
    victim_asset_id = victim_asset.json()["id"]

    attacker_asset = await client.post(
        "/api/v1/assets", headers=attacker_headers, json={"asset_type": "vehicle", "name": "Attacker Truck"}
    )
    attacker_asset_id = attacker_asset.json()["id"]

    device = await client.post(
        "/api/v1/sync/devices", headers=attacker_headers, json={"platform": "ios", "device_name": "Attacker Phone"}
    )
    device_id = device.json()["id"]
    fuel_log_id = "22222222-2222-2222-2222-222222222222"

    create = await client.post(
        "/api/v1/sync/push",
        headers=attacker_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "fuel_log",
                    "id": fuel_log_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"asset_id": attacker_asset_id, "performed_at": "2026-01-01", "gallons": "10"},
                }
            ],
        },
    )
    assert create.json()["results"][0]["status"] == "accepted"

    reassign = await client.post(
        "/api/v1/sync/push",
        headers=attacker_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "fuel_log",
                    "id": fuel_log_id,
                    "base_version": 1,
                    "client_updated_at": "2026-01-02T00:00:00Z",
                    "data": {"asset_id": victim_asset_id, "performed_at": "2026-01-01", "gallons": "10"},
                }
            ],
        },
    )
    result = reassign.json()["results"][0]
    assert result["status"] == "rejected"
    assert result["reason"] == "invalid_reference"
