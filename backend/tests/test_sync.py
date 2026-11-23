# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid
from typing import get_args

from pydantic import BaseModel
from sqlalchemy import select

from app.models.mixins import utcnow
from app.models.sync_device import SyncDevice
from app.schemas.sync import _SYNC_NESTED_MODELS, AssetSyncData, unsupported_sync_fields


async def _register_device(client, auth_headers, name="Test Device") -> str:
    response = await client.post(
        "/api/v1/sync/devices",
        headers=auth_headers,
        json={"platform": "ios", "device_name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_pull_data_is_an_explicit_allowlist_not_every_column(client, auth_headers):
    """Vikunja #44's design-review fix: pull's data payload for each entity
    is built from that entity's own *SyncData schema (the exact same one
    push validates incoming changes against), not a dynamic walk of every
    ORM column. Proves the allowlist is real by asserting pull's data keys
    are *exactly* AssetSyncData's declared fields -- nothing extra, nothing
    from the sync envelope (id/version/updated_at/deleted_at/household_id
    all live as SyncChangeOut's own top-level fields, deliberately not
    duplicated inside data). If a future migration adds a mapped column to
    Asset without also adding it to AssetSyncData, this assertion is what
    keeps that column from silently becoming part of the wire protocol the
    moment the column exists, the same way the old dynamic-walk version
    would have let it."""
    asset_response = await client.post(
        "/api/v1/assets", headers=auth_headers, json={"asset_type": "vehicle", "name": "Allowlist Test Truck"}
    )
    asset_id = asset_response.json()["id"]

    device_id = await _register_device(client, auth_headers)
    pull = await client.post("/api/v1/sync/pull", headers=auth_headers, json={"device_id": device_id})
    assert pull.status_code == 200
    change = next(c for c in pull.json()["changes"] if c["id"] == asset_id)

    assert set(change["data"].keys()) == set(AssetSyncData.model_fields.keys())
    for envelope_field in ("id", "household_id", "version", "updated_at", "deleted_at"):
        assert envelope_field not in change["data"]


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


async def test_maintenance_category_syncs_via_push_and_pull(client, auth_headers):
    device_a = await _register_device(client, auth_headers, "Device A")
    device_b = await _register_device(client, auth_headers, "Device B")

    category_id = str(uuid.uuid4())

    push = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_a,
            "changes": [
                {
                    "entity_type": "maintenance_category",
                    "id": category_id,
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"name": "Wiper Blades"},
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
    assert changes_as_b[category_id]["entity_type"] == "maintenance_category"
    assert changes_as_b[category_id]["data"]["name"] == "Wiper Blades"


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


async def test_vehicle_details_sync_via_push_and_pull(client, auth_headers):
    """vehicle_details (and equipment_details/property_details) previously
    never reached the sync protocol at all -- only the base asset row did,
    so VIN/plate/mileage/etc. set on one device silently never appeared on
    another. Proves that's actually fixed now: a full vehicle_details
    payload (existing fields plus the new per-asset cosmetic/unit-override
    fields) pushed from one device round-trips to a second device's pull."""
    device_a = await _register_device(client, auth_headers, "Device A")
    device_b = await _register_device(client, auth_headers, "Device B")
    asset_id = str(uuid.uuid4())

    push = await client.post(
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
                    "data": {
                        "asset_type": "vehicle",
                        "name": "Ford Focus",
                        "vehicle_details": {
                            "vin": "1FADP3F20EL123456",
                            "make": "Ford",
                            "model": "Focus",
                            "year": 2014,
                            "license_plate": "ABC-1234",
                            "current_mileage": 88000,
                            "mileage_unit": "mi",
                            "fuel_type": "gasoline",
                            "car_display_theme": "amberRetroLCD",
                            "stylized_plate_enabled": True,
                            "unit_system_override": "metric",
                        },
                    },
                }
            ],
        },
    )
    result = push.json()["results"][0]
    assert result["status"] == "accepted"

    pull_as_b = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_b}
    )
    changes_as_b = {c["id"]: c for c in pull_as_b.json()["changes"]}
    vehicle_details = changes_as_b[asset_id]["data"]["vehicle_details"]
    assert vehicle_details["vin"] == "1FADP3F20EL123456"
    assert vehicle_details["license_plate"] == "ABC-1234"
    assert vehicle_details["current_mileage"] == 88000
    assert vehicle_details["car_display_theme"] == "amberRetroLCD"
    assert vehicle_details["stylized_plate_enabled"] is True
    assert vehicle_details["unit_system_override"] == "metric"
    assert changes_as_b[asset_id]["data"]["equipment_details"] is None
    assert changes_as_b[asset_id]["data"]["property_details"] is None

    # Also reachable via the plain REST endpoint, proving the side-table
    # upsert (not just the wire payload) actually landed in vehicle_details.
    get_response = await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert get_response.json()["vehicle_details"]["car_display_theme"] == "amberRetroLCD"


async def test_vehicle_details_sync_update_preserves_fields_not_resent(client, auth_headers):
    """A second push that omits vehicle_details entirely (e.g. an older
    client, or an edit to just the base asset row) must not wipe details a
    prior push already set -- _upsert_asset_details is a no-op when the
    incoming payload's nested object is absent, not a clear."""
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
                    "data": {
                        "asset_type": "vehicle",
                        "name": "Ford Focus",
                        "vehicle_details": {"vin": "1FADP3F20EL123456"},
                    },
                }
            ],
        },
    )

    await client.post(
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
                    "data": {"asset_type": "vehicle", "name": "Ford Focus (renamed)"},
                }
            ],
        },
    )

    get_response = await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    body = get_response.json()
    assert body["name"] == "Ford Focus (renamed)"
    assert body["vehicle_details"]["vin"] == "1FADP3F20EL123456"


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


# ===== attribution and asset ownership over the sync protocol =====


async def _members(client, auth_headers) -> dict:
    response = await client.get("/api/v1/households/members", headers=auth_headers)
    return {m["email"]: m["user_id"] for m in response.json()}


async def _join(client, auth_headers, email: str) -> dict:
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
    return {"Authorization": f"Bearer {register.json()['access_token']}"}


async def test_push_attributes_the_change_to_the_pushing_user(client, auth_headers):
    device_id = await _register_device(client, auth_headers)
    me_id = (await _members(client, auth_headers))["alice@example.com"]
    asset_id = str(uuid.uuid4())

    push = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "id": asset_id,
                    "entity_type": "asset",
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {"asset_type": "vehicle", "name": "Pushed Truck"},
                }
            ],
        },
    )
    assert push.json()["results"][0]["status"] == "accepted"

    other_device = await _register_device(client, auth_headers, name="Reader")
    pull = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"device_id": other_device}
    )
    change = next(c for c in pull.json()["changes"] if c["id"] == asset_id)
    assert change["data"]["updated_by_user_id"] == me_id


async def test_push_cannot_spoof_attribution_to_another_member(client, auth_headers):
    """updated_by_user_id is outbound-only. Full-row push semantics mean a
    client's payload becomes the row, so if this field were trusted anyone
    could credit their edits to someone else. The server must overwrite it."""
    bob_headers = await _join(client, auth_headers, "bob@example.com")
    members = await _members(client, auth_headers)
    alice_id, bob_id = members["alice@example.com"], members["bob@example.com"]

    bob_device = await _register_device(client, bob_headers, name="Bob's Phone")
    asset_id = str(uuid.uuid4())

    push = await client.post(
        "/api/v1/sync/push",
        headers=bob_headers,
        json={
            "device_id": bob_device,
            "changes": [
                {
                    "id": asset_id,
                    "entity_type": "asset",
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {
                        "asset_type": "vehicle",
                        "name": "Not Alice's Doing",
                        # Bob claiming Alice made this change.
                        "updated_by_user_id": alice_id,
                    },
                }
            ],
        },
    )
    assert push.json()["results"][0]["status"] == "accepted"

    reader = await _register_device(client, auth_headers, name="Reader")
    pull = await client.post("/api/v1/sync/pull", headers=auth_headers, json={"device_id": reader})
    change = next(c for c in pull.json()["changes"] if c["id"] == asset_id)
    assert change["data"]["updated_by_user_id"] == bob_id
    assert change["data"]["updated_by_user_id"] != alice_id


async def test_push_rejects_an_owner_from_another_household(client, auth_headers):
    """owner_user_id IS client-settable, so it needs the cross-tenant check
    verify_owned_reference can't express (users have memberships, not a
    household_id)."""
    outsider = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "outsider@example.com",
            "password": "a very good password",
            "display_name": "Outsider",
            "household_name": "Elsewhere",
        },
    )
    outsider_headers = {"Authorization": f"Bearer {outsider.json()['access_token']}"}
    outsider_id = (await _members(client, outsider_headers))["outsider@example.com"]

    device_id = await _register_device(client, auth_headers)
    push = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "id": str(uuid.uuid4()),
                    "entity_type": "asset",
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {
                        "asset_type": "vehicle",
                        "name": "Cross-tenant Owner",
                        "owner_user_id": outsider_id,
                    },
                }
            ],
        },
    )
    result = push.json()["results"][0]
    assert result["status"] == "rejected"
    assert result["reason"] == "invalid_reference"


async def test_push_accepts_an_owner_who_is_a_member(client, auth_headers):
    bob_headers = await _join(client, auth_headers, "bob@example.com")
    assert bob_headers  # joined via the real invite flow
    bob_id = (await _members(client, auth_headers))["bob@example.com"]

    device_id = await _register_device(client, auth_headers)
    asset_id = str(uuid.uuid4())
    push = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "id": asset_id,
                    "entity_type": "asset",
                    "base_version": 0,
                    "client_updated_at": "2026-01-01T00:00:00Z",
                    "data": {
                        "asset_type": "vehicle",
                        "name": "Bob's Truck",
                        "owner_user_id": bob_id,
                    },
                }
            ],
        },
    )
    assert push.json()["results"][0]["status"] == "accepted"

    reader = await _register_device(client, auth_headers, name="Reader")
    pull = await client.post("/api/v1/sync/pull", headers=auth_headers, json={"device_id": reader})
    change = next(c for c in pull.json()["changes"] if c["id"] == asset_id)
    assert change["data"]["owner_user_id"] == bob_id


async def _push_asset(client, auth_headers, device_id, asset_id, base_version, data):
    response = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": asset_id,
                    "base_version": base_version,
                    "client_updated_at": "2026-11-13T00:00:00Z",
                    "data": data,
                }
            ],
        },
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "accepted", result
    return result


async def _pulled_asset(client, auth_headers, device_id, asset_id) -> dict:
    pull = await client.post("/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_id})
    return next(c for c in pull.json()["changes"] if c["id"] == asset_id)["data"]


async def test_sale_price_and_date_sync_via_push_and_pull(client, auth_headers):
    new_app = await _register_device(client, auth_headers, "New App")
    other = await _register_device(client, auth_headers, "Other")
    asset_id = str(uuid.uuid4())
    await _push_asset(
        client,
        auth_headers,
        new_app,
        asset_id,
        0,
        {
            "asset_type": "vehicle",
            "name": "Sold Wagon",
            "status": "archived",
            "purchase_cost": "20000.00",
            "sale_price": "8500.00",
            "sale_date": "2026-10-01",
        },
    )
    data = await _pulled_asset(client, auth_headers, other, asset_id)
    assert data["sale_price"] == "8500.00"
    assert data["sale_date"] == "2026-10-01"


async def test_older_client_omitting_sale_fields_does_not_erase_them(client, auth_headers):
    """An app from before 1.2 doesn't know sale_price/sale_date and leaves
    them out of its full-row push. Full-row semantics would turn that into
    null; the server keeps the stored values instead."""
    new_app = await _register_device(client, auth_headers, "New App")
    old_app = await _register_device(client, auth_headers, "Old App")
    asset_id = str(uuid.uuid4())
    full = {
        "asset_type": "vehicle",
        "name": "Sold Wagon",
        "status": "archived",
        "sale_price": "8500.00",
        "sale_date": "2026-10-01",
    }
    first = await _push_asset(client, auth_headers, new_app, asset_id, 0, full)

    # The old app renames it, knowing nothing about the sale.
    await _push_asset(
        client,
        auth_headers,
        old_app,
        asset_id,
        first["new_version"],
        {"asset_type": "vehicle", "name": "Sold Wagon (renamed)", "status": "archived"},
    )
    data = await _pulled_asset(client, auth_headers, new_app, asset_id)
    assert data["name"] == "Sold Wagon (renamed)"
    assert data["sale_price"] == "8500.00"
    assert data["sale_date"] == "2026-10-01"


async def test_explicit_null_clears_the_sale(client, auth_headers):
    """Un-retiring, or correcting a sale entered by mistake: a client that
    knows the fields sends null and the server clears them."""
    device = await _register_device(client, auth_headers, "New App")
    other = await _register_device(client, auth_headers, "Other")
    asset_id = str(uuid.uuid4())
    sold = {"asset_type": "vehicle", "name": "Wagon", "status": "archived", "sale_price": "100.00", "sale_date": "2026-10-01"}
    first = await _push_asset(client, auth_headers, device, asset_id, 0, sold)
    await _push_asset(
        client,
        auth_headers,
        device,
        asset_id,
        first["new_version"],
        {"asset_type": "vehicle", "name": "Wagon", "status": "active", "sale_price": None, "sale_date": None},
    )
    data = await _pulled_asset(client, auth_headers, other, asset_id)
    assert data["status"] == "active"
    assert data["sale_price"] is None
    assert data["sale_date"] is None


async def test_negative_sale_price_push_is_rejected(client, auth_headers):
    device = await _register_device(client, auth_headers, "App")
    response = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": str(uuid.uuid4()),
                    "base_version": 0,
                    "client_updated_at": "2026-11-14T00:00:00Z",
                    "data": {"asset_type": "vehicle", "name": "Wagon", "status": "archived", "sale_price": "-5.00"},
                }
            ],
        },
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "rejected"
    assert result["reason"] == "validation_error"


# ===== service defaults across the sync protocol, in both client shapes =====


async def test_service_defaults_reach_sync_from_a_pre_move_client_payload(client, auth_headers):
    """A phone that shipped before this table exists writes its remembered specs inside
    `vehicle_details` and reads them back from there. Both directions have to keep working
    after the move, because that build is already installed and is not being rebuilt as part
    of this release.

    The brand rows matter here specifically: build 16 sends them inside `vehicle_details`
    and the server has been dropping them. If they do not land in the table, a second phone
    pulls a null and clears the brand the owner actually chose.
    """
    old_app = await _register_device(client, auth_headers, "Pre-move app")
    other = await _register_device(client, auth_headers, "Other phone")
    asset_id = str(uuid.uuid4())

    await _push_asset(
        client,
        auth_headers,
        old_app,
        asset_id,
        0,
        {
            "asset_type": "vehicle",
            "name": "Dodge Truck",
            "vehicle_details": {
                "make": "Ram",
                "default_oil_viscosity": "5W-30",
                "default_oil_filter_part_number": "PF-63",
                "default_motor_oil_brand": "Valvoline",
            },
        },
    )

    stored = (await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)).json()
    assert stored["service_defaults"]["default_oil_viscosity"] == "5W-30"
    assert stored["service_defaults"]["default_oil_filter_part_number"] == "PF-63"
    assert stored["service_defaults"]["default_motor_oil_brand"] == "Valvoline"

    data = await _pulled_asset(client, auth_headers, other, asset_id)
    # The pre-move client's own read path: still inside vehicle_details.
    assert data["vehicle_details"]["default_oil_viscosity"] == "5W-30"
    assert data["vehicle_details"]["default_oil_filter_part_number"] == "PF-63"
    # A client that knows about the table can read it straight off the same change.
    assert data["service_defaults"]["default_oil_viscosity"] == "5W-30"


async def test_sync_push_without_service_defaults_does_not_clear_them(client, auth_headers):
    """An edit to just the base asset row, or a push from a client that has never heard of
    this table, must not blank out specs another device already saved."""
    device = await _register_device(client, auth_headers, "One app")
    asset_id = str(uuid.uuid4())

    await _push_asset(
        client,
        auth_headers,
        device,
        asset_id,
        0,
        {
            "asset_type": "vehicle",
            "name": "Truck",
            "vehicle_details": {"default_oil_viscosity": "0W-20", "default_coolant_type": "OAT"},
        },
    )
    await _push_asset(
        client, auth_headers, device, asset_id, 1, {"asset_type": "vehicle", "name": "Truck (renamed)"}
    )

    stored = (await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)).json()
    assert stored["name"] == "Truck (renamed)"
    assert stored["service_defaults"]["default_oil_viscosity"] == "0W-20"
    assert stored["vehicle_details"]["default_coolant_type"] == "OAT"


# ===== server 1.6.1: a shipped app clearing a spec (it leaves nulls out) =====


async def _register_device_with(client, auth_headers, name, capabilities):
    response = await client.post(
        "/api/v1/sync/devices",
        headers=auth_headers,
        json={"platform": "ios", "device_name": name, "client_version": "1.5.0 (17)", "capabilities": capabilities},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_a_shipped_app_clearing_a_spec_clears_it(client, auth_headers):
    """The shipped apps encode with defaults off, so a cleared spec is simply missing from
    their full vehicle row. Server 1.6.0 read that as "unknown, keep", so the clear never
    landed -- and the next full-row push from another phone wrote the old value back. A
    legacy-shape vehicle push now means what it meant before 1.6: missing is null."""
    old_app = await _register_device(client, auth_headers, "Shipped 1.4 app")
    other = await _register_device(client, auth_headers, "Other phone")
    asset_id = str(uuid.uuid4())

    first = await _push_asset(
        client,
        auth_headers,
        old_app,
        asset_id,
        0,
        {
            "asset_type": "vehicle",
            "name": "Truck",
            "vehicle_details": {"make": "Ram", "default_oil_viscosity": "0W-20", "default_coolant_type": "OAT"},
        },
    )
    # The owner clears the viscosity: the app sends its row without that key.
    await _push_asset(
        client,
        auth_headers,
        old_app,
        asset_id,
        first["new_version"],
        {"asset_type": "vehicle", "name": "Truck", "vehicle_details": {"make": "Ram", "default_coolant_type": "OAT"}},
    )

    data = await _pulled_asset(client, auth_headers, other, asset_id)
    assert data["vehicle_details"]["default_oil_viscosity"] is None
    assert data["vehicle_details"]["default_coolant_type"] == "OAT"
    assert data["service_defaults"]["default_oil_viscosity"] is None


async def test_a_shipped_app_without_brands_never_blanks_a_brand(client, auth_headers):
    """The 1.4 store builds have no brand fields at all, so a brand missing from their push
    is genuinely unknown to them and must survive their edits."""
    brand_app = await _register_device(client, auth_headers, "Brand-aware app")
    old_app = await _register_device(client, auth_headers, "Shipped 1.4 app")
    asset_id = str(uuid.uuid4())

    first = await _push_asset(
        client,
        auth_headers,
        brand_app,
        asset_id,
        0,
        {"asset_type": "vehicle", "name": "Truck", "vehicle_details": {"default_motor_oil_brand": "Valvoline"}},
    )
    await _push_asset(
        client,
        auth_headers,
        old_app,
        asset_id,
        first["new_version"],
        {"asset_type": "vehicle", "name": "Truck (renamed)", "vehicle_details": {"default_oil_viscosity": "5W-30"}},
    )

    stored = (await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)).json()
    assert stored["service_defaults"]["default_motor_oil_brand"] == "Valvoline"
    assert stored["service_defaults"]["default_oil_viscosity"] == "5W-30"


async def test_an_app_that_declared_brands_can_clear_one(client, auth_headers):
    """A device that said serviceDefaultsBrands holds the brands in its row, so a brand it
    leaves out is one it cleared."""
    app = await _register_device_with(client, auth_headers, "Release-branch app", ["assetDetails", "serviceDefaultsBrands"])
    asset_id = str(uuid.uuid4())

    first = await _push_asset(
        client,
        auth_headers,
        app,
        asset_id,
        0,
        {"asset_type": "vehicle", "name": "Truck", "vehicle_details": {"default_motor_oil_brand": "Valvoline", "default_oil_filter_brand": "WIX"}},
    )
    await _push_asset(
        client,
        auth_headers,
        app,
        asset_id,
        first["new_version"],
        {"asset_type": "vehicle", "name": "Truck", "vehicle_details": {"default_oil_filter_brand": "WIX"}},
    )

    stored = (await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)).json()
    assert stored["service_defaults"]["default_motor_oil_brand"] is None
    assert stored["service_defaults"]["default_oil_filter_brand"] == "WIX"


async def test_a_shipped_app_never_touches_specs_it_has_no_field_for(client, auth_headers):
    """Fuel filter, hydraulic fluid, HVAC and water filters exist only in the new shape; a
    legacy vehicle push cannot know them and leaves them alone."""
    new_app = await _register_device(client, auth_headers, "New app")
    old_app = await _register_device(client, auth_headers, "Shipped 1.4 app")
    asset_id = str(uuid.uuid4())

    first = await _push_asset(
        client,
        auth_headers,
        new_app,
        asset_id,
        0,
        {
            "asset_type": "vehicle",
            "name": "Truck",
            "vehicle_details": {"make": "Ram"},
            "service_defaults": {"default_oil_viscosity": "5W-30", "default_fuel_filter_part_number": "FF-1"},
        },
    )
    await _push_asset(
        client,
        auth_headers,
        old_app,
        asset_id,
        first["new_version"],
        {"asset_type": "vehicle", "name": "Truck", "vehicle_details": {"make": "Ram", "default_oil_viscosity": "5W-30"}},
    )

    stored = (await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)).json()
    assert stored["service_defaults"]["default_fuel_filter_part_number"] == "FF-1"
    assert stored["service_defaults"]["default_oil_viscosity"] == "5W-30"


async def test_the_new_shape_stays_key_presence_aware(client, auth_headers):
    """A client that sends service_defaults is the authority on it, field by field: a key it
    leaves out there is kept, whatever its vehicle_details copy omits."""
    new_app = await _register_device(client, auth_headers, "New app")
    asset_id = str(uuid.uuid4())

    first = await _push_asset(
        client,
        auth_headers,
        new_app,
        asset_id,
        0,
        {"asset_type": "vehicle", "name": "Truck", "service_defaults": {"default_oil_viscosity": "5W-30", "default_coolant_type": "OAT"}},
    )
    await _push_asset(
        client,
        auth_headers,
        new_app,
        asset_id,
        first["new_version"],
        {"asset_type": "vehicle", "name": "Truck", "vehicle_details": {"make": "Ram"}, "service_defaults": {"default_coolant_type": "HOAT"}},
    )

    stored = (await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)).json()
    assert stored["service_defaults"]["default_oil_viscosity"] == "5W-30"
    assert stored["service_defaults"]["default_coolant_type"] == "HOAT"


async def test_vehicle_details_on_another_type_clears_nothing(client, auth_headers):
    """Only a vehicle's own row is complete. A stray vehicle_details object on an equipment
    change stays key-presence-aware, so it cannot blank the equipment's specs."""
    app = await _register_device(client, auth_headers, "App")
    asset_id = str(uuid.uuid4())

    first = await _push_asset(
        client,
        auth_headers,
        app,
        asset_id,
        0,
        {"asset_type": "equipment", "name": "Mower", "service_defaults": {"default_oil_viscosity": "SAE 30"}},
    )
    await _push_asset(
        client,
        auth_headers,
        app,
        asset_id,
        first["new_version"],
        {"asset_type": "equipment", "name": "Mower", "vehicle_details": {"make": "Toro"}},
    )

    stored = (await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)).json()
    assert stored["service_defaults"]["default_oil_viscosity"] == "SAE 30"


async def test_a_vehicle_with_nothing_saved_gets_no_row(client, auth_headers):
    """A legacy push with no specs at all is "nothing saved", not a row of nulls."""
    app = await _register_device(client, auth_headers, "Shipped 1.4 app")
    asset_id = str(uuid.uuid4())
    await _push_asset(client, auth_headers, app, asset_id, 0, {"asset_type": "vehicle", "name": "Truck", "vehicle_details": {"make": "Ram"}})

    stored = (await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)).json()
    assert stored.get("service_defaults") is None


# ===== the server says what it can store, and says it loudly (Vikunja #828) =====


def _nested_payload_fields(model) -> set[str]:
    """Field names whose declared type is another payload schema, Optional unwrapped."""
    names = set()
    for name, info in model.model_fields.items():
        for candidate in (info.annotation, *get_args(info.annotation)):
            if isinstance(candidate, type) and issubclass(candidate, BaseModel):
                names.add(name)
                break
    return names


def test_the_nested_map_covers_every_nested_payload_the_asset_change_declares():
    """unsupported_sync_fields can only look inside a nested object whose shape it knows.
    A nested schema added to AssetSyncData but not to that map would have its unknown keys
    reported as top-level ones, which is wrong in a way a client cannot see. So the map is
    asserted against the schema rather than kept in sync by whoever remembers it."""
    assert _nested_payload_fields(AssetSyncData) == set(_SYNC_NESTED_MODELS)


async def test_pull_advertises_the_field_families_it_can_store(client, auth_headers):
    """Every pull answers what this server can actually hold, unprompted. A client that has
    never heard of the key ignores it; a client that has can refuse to offer a field before
    the user types anything into it. Derived from the payload schemas, so a capability that
    the schema cannot back is not advertiseable."""
    device = await _register_device(client, auth_headers, "Any app")

    pull = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device}
    )
    capabilities = set(pull.json()["server_capabilities"])

    assert {"assetDetails", "serviceDefaults", "serviceDefaultsBrands"} <= capabilities
    # The server is ahead of the shipped apps here on purpose: the equipment and property
    # specs already have a column, a sync field and a REST field, while the screens that
    # would ask for them are still cards #825/#826. Advertising the storage half is what
    # lets a client know it may send them.
    assert {"equipmentServiceDefaults", "propertyServiceDefaults"} <= capabilities


def test_a_capability_needs_a_column_not_only_a_wire_field(monkeypatch):
    """The gating is the entire point of a capability tag, so it gets tested directly: strip
    the columns out from under it and the tags fall, even though every payload schema still
    declares every field. Telling a client "brands are supported" and then dropping them is
    the bug this card was opened for, so a tag is not allowed to survive on the wire's word
    alone -- only on the wire AND a column that survives a restart."""
    import app.schemas.sync as sync_schemas

    monkeypatch.setattr(
        sync_schemas,
        "_STORED_SERVICE_DEFAULT_FIELDS",
        frozenset({"default_oil_viscosity"}),
    )
    capabilities = sync_schemas.server_capabilities()

    assert "serviceDefaults" in capabilities
    assert "serviceDefaultsBrands" not in capabilities
    assert "equipmentServiceDefaults" not in capabilities
    assert "propertyServiceDefaults" not in capabilities


async def test_push_reports_the_fields_it_has_nowhere_to_put(client, auth_headers):
    """The half that stops data loss: a payload carrying a field this server does not know
    is still accepted -- the rest of the row is real, and an old phone has to keep syncing
    -- but the keys with nowhere to go come back named. Before this, Pydantic dropped them
    silently and "accepted" was a lie: the client believed the value was saved, sent it to
    no one else, and the owner found out when a second device showed the field empty."""
    device = await _register_device(client, auth_headers, "App ahead of the server")
    asset_id = str(uuid.uuid4())

    result = await _push_asset(
        client,
        auth_headers,
        device,
        asset_id,
        0,
        {
            "asset_type": "vehicle",
            "name": "Truck",
            # A field the client would like the server to have. Top level: not declared.
            "default_gasket_type": "Fel-Pro",
            "vehicle_details": {
                "make": "Ram",
                # The shape of the brand bug found on #823: close to a real field name,
                # so nothing about the push looks wrong to the client that sent it.
                "default_oil_brand": "Valvoline",
            },
        },
    )

    assert result["status"] == "accepted"
    assert set(result["unsupported_fields"]) == {
        "default_gasket_type",
        # Dot-separated: a nested key cannot hide behind the name of the object that
        # carried it, and a client can point at the exact field it sent.
        "vehicle_details.default_oil_brand",
    }

    # And the part it *can* store is stored, unchanged. What it could not store left no
    # row behind: absence stays absence, rather than becoming an empty row of nulls that
    # then syncs out to every other device as "the user cleared these".
    stored = (await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)).json()
    assert stored["name"] == "Truck"
    assert stored["vehicle_details"]["make"] == "Ram"
    assert stored["service_defaults"] is None


async def test_fields_the_server_can_store_are_not_reported_as_unsupported(client, auth_headers):
    """The false-alarm half of the same contract. This is build 16's actual payload shape:
    brands inside `vehicle_details`, plus a spec only the new table carries. A client that
    obeys unsupported_fields would start holding back fields it saves perfectly well, so an
    accepted payload must come back with nothing in that list."""
    device = await _register_device(client, auth_headers, "Build 16")
    asset_id = str(uuid.uuid4())

    result = await _push_asset(
        client,
        auth_headers,
        device,
        asset_id,
        0,
        {
            "asset_type": "vehicle",
            "name": "Truck",
            "vehicle_details": {
                "make": "Ram",
                "default_oil_viscosity": "5W-30",
                "default_motor_oil_brand": "Valvoline",
                "default_oil_filter_brand": "Fram",
                "default_air_filter_brand": "Fram",
            },
            "service_defaults": {"default_hvac_filter_size": "20x25x1"},
        },
    )

    assert result["unsupported_fields"] == []

    stored = (await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)).json()
    assert stored["service_defaults"]["default_motor_oil_brand"] == "Valvoline"
    assert stored["vehicle_details"]["default_air_filter_brand"] == "Fram"
    assert stored["service_defaults"]["default_hvac_filter_size"] == "20x25x1"


def test_the_unsupported_field_check_looks_inside_nested_payloads():
    """Pure form of the same rule, no HTTP: nested unknown keys are named with their path,
    known ones are not named, and a payload that is entirely understood returns empty."""
    assert (
        unsupported_sync_fields(
            AssetSyncData,
            {
                "asset_type": "vehicle",
                "name": "Truck",
                "service_defaults": {"default_oil_viscosity": "5W-30", "made_up_spec": "x"},
            },
        )
        == ["service_defaults.made_up_spec"]
    )


async def _declared_push(client, auth_headers, device_id, asset_id, base_version, data, **declaration):
    """Push with an optional device declaration riding alongside the changes."""
    response = await client.post(
        "/api/v1/sync/push",
        headers=auth_headers,
        json={
            "device_id": device_id,
            "changes": [
                {
                    "entity_type": "asset",
                    "id": asset_id,
                    "base_version": base_version,
                    "client_updated_at": "2026-11-13T00:00:00Z",
                    "data": data,
                }
            ],
            **declaration,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["results"][0]


async def _device_row(client, auth_headers, device_id) -> dict:
    listing = await client.get("/api/v1/sync/devices", headers=auth_headers)
    return next(d for d in listing.json() if d["id"] == device_id)


async def test_a_device_that_says_what_it_can_do_is_remembered_saying_it(client, auth_headers):
    """The client half of #828, server side. A pairing that declares its app version and the
    field families it understands has both kept, and both visible on the device list --
    because a household with one negotiating phone and one legacy phone is a household where
    the two devices are storing different amounts of the same row, and until now nothing in
    the API could show that."""
    response = await client.post(
        "/api/v1/sync/devices",
        headers=auth_headers,
        json={
            "platform": "ios",
            "device_name": "Phone on build 17",
            "client_version": "1.5.0 (16)",
            "capabilities": ["serviceDefaults", "serviceDefaultsBrands"],
        },
    )
    assert response.status_code == 201, response.text
    device_id = response.json()["id"]

    row = await _device_row(client, auth_headers, device_id)
    assert row["client_version"] == "1.5.0 (16)"
    assert set(row["capabilities"]) == {"serviceDefaults", "serviceDefaultsBrands"}
    assert row["capabilities_reported_at"] is not None

    pull = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_id}
    )
    assert set(pull.json()["device_capabilities"]) == {"serviceDefaults", "serviceDefaultsBrands"}
    assert pull.json()["device_client_version"] == "1.5.0 (16)"


async def test_a_device_that_said_nothing_is_known_as_having_said_nothing(client, auth_headers):
    """The distinction the whole compatibility story rests on. A phone paired before the
    handshake exists is a legacy superset client and keeps getting everything; a phone that
    deliberately declared an empty capability list would mean something else, and the server
    must not confuse the two. So NULL is stored as NULL and echoed as None, never backfilled
    into []."""
    device_id = await _register_device(client, auth_headers, "Phone paired in 2025")

    row = await _device_row(client, auth_headers, device_id)
    assert row["client_version"] is None
    assert row["capabilities"] is None
    assert row["capabilities_reported_at"] is None

    pull = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_id}
    )
    assert pull.json()["device_capabilities"] is None
    # The server still advertises everything it can hold, to a legacy client, unprompted:
    # legacy means "serve the old shapes too", never "this device gets nothing".
    assert "serviceDefaults" in pull.json()["server_capabilities"]


async def test_an_app_that_upgrades_mid_life_says_so_on_an_ordinary_push(client, auth_headers):
    """No second round trip and no new endpoint: the declaration rides along with a push, so
    a device that updated its app starts negotiating on the next sync rather than the next
    re-pairing (which is the one thing users should never have to do to keep their data)."""
    device_id = await _register_device(client, auth_headers, "Phone that will upgrade")
    asset_id = str(uuid.uuid4())

    await _declared_push(
        client,
        auth_headers,
        device_id,
        asset_id,
        0,
        {"asset_type": "vehicle", "name": "Truck", "vehicle_details": {"make": "Ram"}},
        client_version="1.6.0 (20)",
        capabilities=["serviceDefaults", "equipmentServiceDefaults"],
    )

    row = await _device_row(client, auth_headers, device_id)
    assert row["client_version"] == "1.6.0 (20)"
    assert set(row["capabilities"]) == {"serviceDefaults", "equipmentServiceDefaults"}
    assert row["capabilities_reported_at"] is not None


async def test_a_push_that_says_nothing_about_itself_keeps_what_it_already_said(client, auth_headers):
    """Presence rule again, applied to the device itself. Most pushes are an app that has not
    thought about capabilities at all; if an omitted key were read as an empty declaration,
    every sync from a negotiating device would erase its own negotiation and drop it back to
    legacy treatment."""
    response = await client.post(
        "/api/v1/sync/devices",
        headers=auth_headers,
        json={
            "platform": "android",
            "device_name": "Tablet",
            "client_version": "1.5.0 (16)",
            "capabilities": ["serviceDefaults"],
        },
    )
    device_id = response.json()["id"]

    await _push_asset(client, auth_headers, device_id, str(uuid.uuid4()), 0, {
        "asset_type": "vehicle",
        "name": "Truck",
        "vehicle_details": {"make": "Ram"},
    })

    row = await _device_row(client, auth_headers, device_id)
    assert row["client_version"] == "1.5.0 (16)"
    assert row["capabilities"] == ["serviceDefaults"]


async def test_a_client_cannot_declare_itself_into_a_feature(client, auth_headers):
    """Declaring a capability is information about the client, not permission from the server.
    What this build can hold is derived from its own schemas and columns alone, so a client
    that names a capability the server has never heard of gains nothing -- the field it wants
    still comes back named as unsupported."""
    response = await client.post(
        "/api/v1/sync/devices",
        headers=auth_headers,
        json={
            "platform": "ios",
            "device_name": "Optimistic app",
            "client_version": "9.9.9",
            "capabilities": ["serviceDefaultsV2"],
        },
    )
    device_id = response.json()["id"]
    asset_id = str(uuid.uuid4())

    result = await _push_asset(client, auth_headers, device_id, asset_id, 0, {
        "asset_type": "vehicle",
        "name": "Truck",
        # A field this build has no column for, named the way a future schema would name it.
        "service_defaults": {"default_gasket_type": "Fel-Pro"},
    })

    assert "service_defaults.default_gasket_type" in result["unsupported_fields"]

    pull = await client.post(
        "/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device_id}
    )
    assert "serviceDefaultsV2" not in pull.json()["server_capabilities"]
    # ... while the server still remembers the device claimed it. Kept, not trusted.
    assert pull.json()["device_capabilities"] == ["serviceDefaultsV2"]


# ---------------------------------------------------------------------------
# Equipment fill-up reading: hours or odometer (equipment_details.fuel_reading_unit)
# ---------------------------------------------------------------------------


def _mower(**equipment):
    return {"asset_type": "equipment", "name": "Mower", "equipment_details": {"manufacturer": "Toro", **equipment}}


async def test_an_equipment_fill_up_unit_syncs_to_other_devices(client, auth_headers):
    phone = await _register_device(client, auth_headers, "Phone")
    tablet = await _register_device(client, auth_headers, "Tablet")
    asset_id = str(uuid.uuid4())
    await _push_asset(client, auth_headers, phone, asset_id, 0, _mower(fuel_reading_unit="odometer"))

    pulled = await _pulled_asset(client, auth_headers, tablet, asset_id)
    assert pulled["equipment_details"]["fuel_reading_unit"] == "odometer"


async def test_an_app_without_the_field_keeps_the_choice(client, auth_headers):
    """1.5.x apps send a full equipment row with no fuel_reading_unit key. Editing the
    mower's name on one of those must not quietly switch it back to hours."""
    new_app = await _register_device(client, auth_headers, "New app")
    old_app = await _register_device(client, auth_headers, "Old app")
    asset_id = str(uuid.uuid4())
    first = await _push_asset(client, auth_headers, new_app, asset_id, 0, _mower(fuel_reading_unit="odometer"))

    await _push_asset(
        client, auth_headers, old_app, asset_id, first["new_version"], {**_mower(), "name": "Riding Mower"}
    )

    pulled = await _pulled_asset(client, auth_headers, new_app, asset_id)
    assert pulled["name"] == "Riding Mower"
    assert pulled["equipment_details"]["fuel_reading_unit"] == "odometer"


async def test_an_explicit_null_goes_back_to_hours(client, auth_headers):
    phone = await _register_device(client, auth_headers, "Phone")
    reader = await _register_device(client, auth_headers, "Reader")
    asset_id = str(uuid.uuid4())
    first = await _push_asset(client, auth_headers, phone, asset_id, 0, _mower(fuel_reading_unit="odometer"))
    await _push_asset(client, auth_headers, phone, asset_id, first["new_version"], _mower(fuel_reading_unit=None))

    pulled = await _pulled_asset(client, auth_headers, reader, asset_id)
    assert pulled["equipment_details"]["fuel_reading_unit"] is None


async def test_the_fill_up_unit_is_advertised_and_not_reported_unsupported(client, auth_headers):
    device = await _register_device(client, auth_headers, "Any app")
    pull = await client.post("/api/v1/sync/pull", headers=auth_headers, json={"cursor": None, "device_id": device})
    assert "equipmentFuelReading" in pull.json()["server_capabilities"]

    result = await _push_asset(client, auth_headers, device, str(uuid.uuid4()), 0, _mower(fuel_reading_unit="hours"))
    assert "equipment_details.fuel_reading_unit" not in (result.get("unsupported_fields") or [])
