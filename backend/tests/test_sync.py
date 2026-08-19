import uuid

from sqlalchemy import select

from app.models.mixins import utcnow
from app.models.sync_device import SyncDevice


async def _register_device(client, auth_headers, name="Test Device") -> str:
    response = await client.post(
        "/api/v1/sync/devices",
        headers=auth_headers,
        json={"platform": "ios", "device_name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_push_creates_new_entity(client, auth_headers):
    device_id = await _register_device(client, auth_headers)
    asset_id = str(uuid.uuid4())

    response = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": asset_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"asset_type": "equipment", "name": "Snow Blower"},
                }
            ],
        },
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "accepted"
    assert result["new_version"] == 1

    get_response = await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Snow Blower"


async def test_push_update_bumps_version(client, auth_headers):
    device_id = await _register_device(client, auth_headers)
    asset_id = str(uuid.uuid4())

    await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": asset_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"asset_type": "equipment", "name": "Snow Blower"},
                }
            ],
        },
    )

    response = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": asset_id,
                    "base_version": 1,
                    "client_updated_at": "2026-01-02T00:00:00Z",
                    "data": {"asset_type": "equipment", "name": "Riding Snow Blower"},
                }
            ],
        },
    )
    result = response.json()["results"][0]
    assert result["status"] == "accepted"
    assert result["new_version"] == 2


async def test_push_delete_soft_deletes_and_is_reflected_in_pull(client, auth_headers):
    device_a = await _register_device(client, auth_headers, "Device A")
    device_b = await _register_device(client, auth_headers, "Device B")
    asset_id = str(uuid.uuid4())

    await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_a,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": asset_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"asset_type": "equipment", "name": "Snow Blower"},
                }
            ],
        },
    )

    delete_response = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_a,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": asset_id,
                    "base_version": 1,
                    "client_updated_at": "2026-01-02T00:00:00Z",
                    "data": {},
                    "deleted": True,
                }
            ],
        },
    )
    result = delete_response.json()["results"][0]
    assert result["status"] == "accepted"
    assert result["new_version"] == 2

    get_response = await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert get_response.status_code == 404

    pull_as_b = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_b}
    )
    changes_as_b = {c["id"]: c for c in pull_as_b.json()["changes"]}
    assert changes_as_b[asset_id]["deleted"] is True


async def test_push_delete_of_never_synced_entity_is_a_harmless_noop(client, auth_headers):
    device_id = await _register_device(client, auth_headers)
    never_existed_id = str(uuid.uuid4())

    response = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": never_existed_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {},
                    "deleted": True,
                }
            ],
        },
    )
    result = response.json()["results"][0]
    assert result["status"] == "accepted"

    get_response = await client.get(f"/api/v1/assets/{never_existed_id}", headers=auth_headers)
    assert get_response.status_code == 404


async def test_push_stale_base_version_returns_conflict(client, auth_headers):
    device_id = await _register_device(client, auth_headers)
    asset_id = str(uuid.uuid4())

    await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": asset_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"asset_type": "equipment", "name": "Snow Blower"},
                }
            ],
        },
    )

    response = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": asset_id,
                    "base_version": 0,  # stale — server is already at version 1
                    "client_updated_at": "2026-01-02T00:00:00Z",
                    "data": {"asset_type": "equipment", "name": "Conflicting Name"},
                }
            ],
        },
    )
    result = response.json()["results"][0]
    assert result["status"] == "conflict"
    assert result["server_version"] == 1
    assert result["server_data"]["name"] == "Snow Blower"


async def test_push_batch_one_bad_row_does_not_block_others(client, auth_headers):
    device_id = await _register_device(client, auth_headers)
    good_id = str(uuid.uuid4())
    bad_id = str(uuid.uuid4())

    response = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": bad_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"name": "Missing asset_type"},  # invalid — asset_type is required
                },
                {
                    "entity_type": "asset",
                    "id": good_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"asset_type": "equipment", "name": "Leaf Blower"},
                },
                {
                    "entity_type": "not_a_real_entity",
                    "id": str(uuid.uuid4()),
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {},
                },
            ],
        },
    )
    results = response.json()["results"]
    assert results[0]["status"] == "rejected"
    assert results[0]["reason"] == "validation_error"
    assert results[1]["status"] == "accepted"
    assert results[2]["status"] == "rejected"
    assert results[2]["reason"] == "unknown_entity_type"

    get_response = await client.get(f"/api/v1/assets/{good_id}", headers=auth_headers)
    assert get_response.status_code == 200


async def test_pull_excludes_own_device_echo_but_not_other_devices(client, auth_headers):
    device_a = await _register_device(client, auth_headers, "Device A")
    device_b = await _register_device(client, auth_headers, "Device B")
    asset_id = str(uuid.uuid4())

    await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_a,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": asset_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"asset_type": "equipment", "name": "Generator"},
                }
            ],
        },
    )

    pull_as_a = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_a}
    )
    assert asset_id not in [c["id"] for c in pull_as_a.json()["changes"]]

    pull_as_b = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_b}
    )
    changes_as_b = {c["id"]: c for c in pull_as_b.json()["changes"]}
    assert asset_id in changes_as_b
    assert changes_as_b[asset_id]["data"]["name"] == "Generator"
    assert changes_as_b[asset_id]["deleted"] is False


async def test_pull_reports_soft_deleted_rows(client, auth_headers):
    await _register_device(client, auth_headers, "Device A")
    device_b = await _register_device(client, auth_headers, "Device B")

    create = await client.post(
        "/api/v1/assets", headers=auth_headers, json={"asset_type": "equipment", "name": "Old Mower"}
    )
    asset_id = create.json()["id"]
    await client.delete(f"/api/v1/assets/{asset_id}", headers=auth_headers)

    pull_as_b = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_b}
    )
    changes_as_b = {c["id"]: c for c in pull_as_b.json()["changes"]}
    assert changes_as_b[asset_id]["deleted"] is True


async def test_pull_cursor_pagination_is_incremental(client, auth_headers):
    await _register_device(client, auth_headers, "Device A")
    device_b = await _register_device(client, auth_headers, "Device B")

    first_asset = (
        await client.post("/api/v1/assets", headers=auth_headers, json={"asset_type": "equipment", "name": "First"})
    ).json()["id"]

    first_pull = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_b}
    )
    body = first_pull.json()
    assert [c["id"] for c in body["changes"]] == [first_asset]
    cursor = body["next_cursor"]

    second_asset = (
        await client.post("/api/v1/assets", headers=auth_headers, json={"asset_type": "equipment", "name": "Second"})
    ).json()["id"]

    second_pull = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": cursor, "device_id": device_b}
    )
    assert [c["id"] for c in second_pull.json()["changes"]] == [second_asset]


async def test_revoked_device_is_rejected(client, auth_headers, db_session):
    device_id = await _register_device(client, auth_headers)

    result = await db_session.execute(select(SyncDevice).where(SyncDevice.id == uuid.UUID(device_id)))
    device = result.scalar_one()
    device.revoked_at = utcnow()
    await db_session.commit()

    response = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_id}
    )
    assert response.status_code == 403


async def test_fuel_log_syncs_via_push_and_pull(client, auth_headers):
    device_a = await _register_device(client, auth_headers, "Device A")
    device_b = await _register_device(client, auth_headers, "Device B")

    asset_id = (
        await client.post("/api/v1/assets", headers=auth_headers, json={"asset_type": "vehicle", "name": "Truck"})
    ).json()["id"]
    fuel_log_id = str(uuid.uuid4())

    push = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_a,
            "changes": [
                {
                    "entity_type": "fuel_log",
                    "id": fuel_log_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"asset_id": asset_id, "performed_at": "2026-01-01", "gallons": "12.5"},
                }
            ],
        },
    )
    result = push.json()["results"][0]
    assert result["status"] == "accepted"
    assert result["new_version"] == 1

    pull_as_b = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_b}
    )
    changes_as_b = {c["id"]: c for c in pull_as_b.json()["changes"]}
    assert changes_as_b[fuel_log_id]["entity_type"] == "fuel_log"
    assert changes_as_b[fuel_log_id]["data"]["gallons"] == "12.500"


async def test_trip_log_syncs_via_push_and_pull(client, auth_headers):
    device_a = await _register_device(client, auth_headers, "Device A")
    device_b = await _register_device(client, auth_headers, "Device B")

    asset_id = (
        await client.post("/api/v1/assets", headers=auth_headers, json={"asset_type": "vehicle", "name": "Truck"})
    ).json()["id"]
    trip_log_id = str(uuid.uuid4())

    push = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_a,
            "changes": [
                {
                    "entity_type": "trip_log",
                    "id": trip_log_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {
                        "asset_id": asset_id,
                        "performed_at": "2026-01-01T09:00:00Z",
                        "purpose": "business",
                        "end_odometer": "41542.0",
                        "distance": "42.0",
                    },
                }
            ],
        },
    )
    result = push.json()["results"][0]
    assert result["status"] == "accepted"
    assert result["new_version"] == 1

    pull_as_b = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_b}
    )
    changes_as_b = {c["id"]: c for c in pull_as_b.json()["changes"]}
    assert changes_as_b[trip_log_id]["entity_type"] == "trip_log"
    assert changes_as_b[trip_log_id]["data"]["distance"] == "42.0"


# --- Revoking a lost or stolen paired device (Vikunja #36) ---
#
# SyncDevice.revoked_at and its enforcement in _get_active_device already
# existed; nothing could SET it, so the check could never fire.


async def test_list_devices_returns_household_devices(client, auth_headers):
    first = await client.post(
        "/api/v1/sync/devices", headers=auth_headers, json={"platform": "ios", "device_name": "Phone"}
    )
    await client.post(
        "/api/v1/sync/devices", headers=auth_headers, json={"platform": "web", "device_name": "Laptop"}
    )
    listing = await client.get("/api/v1/sync/devices", headers=auth_headers)
    assert listing.status_code == 200
    names = [d["device_name"] for d in listing.json()]
    assert "Phone" in names and "Laptop" in names
    assert all(d["revoked_at"] is None for d in listing.json())
    assert first.json()["id"] in [d["id"] for d in listing.json()]


async def test_revoked_device_can_no_longer_sync(client, auth_headers):
    device = await client.post(
        "/api/v1/sync/devices", headers=auth_headers, json={"platform": "ios", "device_name": "Stolen Phone"}
    )
    device_id = device.json()["id"]

    # Works before revocation.
    before = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"device_id": device_id}
    )
    assert before.status_code == 200

    revoke = await client.delete(f"/api/v1/sync/devices/{device_id}", headers=auth_headers)
    assert revoke.status_code == 204

    # Both directions must stop working, not just one.
    after_pull = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"device_id": device_id}
    )
    assert after_pull.status_code == 403

    after_push = await client.post(
        "/api/v1/sync/push", headers=auth_headers, json={"device_id": device_id, "changes": []}
    )
    assert after_push.status_code == 403


async def test_revoking_is_idempotent_and_device_stays_listed(client, auth_headers):
    device = await client.post(
        "/api/v1/sync/devices", headers=auth_headers, json={"platform": "android", "device_name": "Tablet"}
    )
    device_id = device.json()["id"]

    assert (await client.delete(f"/api/v1/sync/devices/{device_id}", headers=auth_headers)).status_code == 204
    # Second revoke is a no-op, not an error -- the caller's intent is met.
    assert (await client.delete(f"/api/v1/sync/devices/{device_id}", headers=auth_headers)).status_code == 204

    # Still listed, with a revoked_at -- "revoked on the 3rd" is the useful
    # answer after losing a device, and hiding it invites doubt that the
    # revoke worked.
    listing = await client.get("/api/v1/sync/devices", headers=auth_headers)
    revoked = [d for d in listing.json() if d["id"] == device_id]
    assert len(revoked) == 1
    assert revoked[0]["revoked_at"] is not None
