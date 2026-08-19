"""Maintenance records API (2026-08-19 review, D3 / Vikunja #37).

Records had no dedicated test file despite being the entity the whole product
is named around. Cross-household coverage lives in test_household_isolation.py;
this covers the ordinary CRUD surface and the schedule linkage.
"""

import uuid


async def _asset(client, auth_headers) -> str:
    response = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={"asset_type": "vehicle", "name": "Estate Car"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _schedule(client, auth_headers, asset_id: str) -> str:
    response = await client.post(
        "/api/v1/maintenance-schedules",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "name": "Oil change",
            "interval_type": "time",
            "interval_days": 180,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_create_and_fetch_a_record(client, auth_headers):
    asset_id = await _asset(client, auth_headers)
    created = await client.post(
        "/api/v1/maintenance-records",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-03-01",
            "category": "oil_change",
            "description": "Full synthetic",
            "cost": "89.99",
            "odometer_reading": 51234,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["category"] == "oil_change"
    assert body["odometer_reading"] == 51234
    # Money must survive the round trip exactly -- a float here would be a bug.
    assert str(body["cost"]) == "89.99"

    fetched = await client.get(f"/api/v1/maintenance-records/{body['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["description"] == "Full synthetic"


async def test_record_can_be_linked_to_a_schedule(client, auth_headers):
    asset_id = await _asset(client, auth_headers)
    schedule_id = await _schedule(client, auth_headers, asset_id)

    created = await client.post(
        "/api/v1/maintenance-records",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-03-01",
            "category": "oil_change",
            "schedule_id": schedule_id,
        },
    )
    assert created.status_code == 201
    assert created.json()["schedule_id"] == schedule_id


async def test_records_can_be_filtered_by_asset(client, auth_headers):
    first = await _asset(client, auth_headers)
    second = (
        await client.post(
            "/api/v1/assets",
            headers=auth_headers,
            json={"asset_type": "equipment", "name": "Mower"},
        )
    ).json()["id"]

    for asset_id, category in ((first, "oil_change"), (second, "blade_sharpening")):
        await client.post(
            "/api/v1/maintenance-records",
            headers=auth_headers,
            json={"asset_id": asset_id, "performed_at": "2026-03-01", "category": category},
        )

    filtered = await client.get(
        f"/api/v1/maintenance-records?asset_id={second}", headers=auth_headers
    )
    assert filtered.status_code == 200
    assert [r["category"] for r in filtered.json()] == ["blade_sharpening"]


async def test_partial_update_leaves_other_fields_alone(client, auth_headers):
    asset_id = await _asset(client, auth_headers)
    record_id = (
        await client.post(
            "/api/v1/maintenance-records",
            headers=auth_headers,
            json={
                "asset_id": asset_id,
                "performed_at": "2026-03-01",
                "category": "brakes",
                "description": "Front pads",
            },
        )
    ).json()["id"]

    updated = await client.patch(
        f"/api/v1/maintenance-records/{record_id}",
        headers=auth_headers,
        json={"cost": "42.50"},
    )
    assert updated.status_code == 200
    assert str(updated.json()["cost"]) == "42.50"
    assert updated.json()["description"] == "Front pads"
    assert updated.json()["category"] == "brakes"


async def test_deleted_record_disappears_from_reads(client, auth_headers):
    asset_id = await _asset(client, auth_headers)
    record_id = (
        await client.post(
            "/api/v1/maintenance-records",
            headers=auth_headers,
            json={"asset_id": asset_id, "performed_at": "2026-03-01", "category": "inspection"},
        )
    ).json()["id"]

    assert (
        await client.delete(f"/api/v1/maintenance-records/{record_id}", headers=auth_headers)
    ).status_code == 204

    # Soft delete: the row survives for sync tombstoning, but reads must not
    # see it.
    assert (
        await client.get(f"/api/v1/maintenance-records/{record_id}", headers=auth_headers)
    ).status_code == 404
    assert (await client.get("/api/v1/maintenance-records", headers=auth_headers)).json() == []


async def test_unknown_record_is_404(client, auth_headers):
    response = await client.get(f"/api/v1/maintenance-records/{uuid.uuid4()}", headers=auth_headers)
    assert response.status_code == 404


async def test_record_requires_an_asset_that_exists(client, auth_headers):
    response = await client.post(
        "/api/v1/maintenance-records",
        headers=auth_headers,
        json={
            "asset_id": str(uuid.uuid4()),
            "performed_at": "2026-03-01",
            "category": "oil_change",
        },
    )
    assert response.status_code == 404
