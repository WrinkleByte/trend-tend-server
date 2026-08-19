"""Maintenance schedules API (2026-08-19 review, D3 / Vikunja #37).

These had zero dedicated tests, which is notable because schedules carry the
recurrence engine — the most logic-dense part of the domain. `test_recurrence.py`
covers that engine's pure functions; this file covers the endpoint layer around
it, including the due-status fields the API computes on read rather than stores.
"""

import uuid
from datetime import UTC, datetime, timedelta


def _today():
    # Match the server, which computes due status in UTC (see
    # api/v1/maintenance_schedules.py's _to_response). Using local
    # date.today() here would make these tests flap around midnight.
    return datetime.now(UTC).date()


async def _asset(client, auth_headers, **overrides) -> str:
    payload = {"asset_type": "vehicle", "name": "Truck"}
    payload.update(overrides)
    response = await client.post("/api/v1/assets", headers=auth_headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_create_and_fetch_a_time_based_schedule(client, auth_headers):
    asset_id = await _asset(client, auth_headers)
    created = await client.post(
        "/api/v1/maintenance-schedules",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "name": "Oil change",
            "interval_type": "time",
            "interval_days": 90,
            "anchor_date": "2026-01-01",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Oil change"
    assert body["interval_days"] == 90
    assert body["active"] is True

    fetched = await client.get(f"/api/v1/maintenance-schedules/{body['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


async def test_next_due_date_is_derived_from_the_anchor(client, auth_headers):
    asset_id = await _asset(client, auth_headers)
    anchor = _today() - timedelta(days=10)
    created = await client.post(
        "/api/v1/maintenance-schedules",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "name": "Air filter",
            "interval_type": "time",
            "interval_days": 30,
            "anchor_date": anchor.isoformat(),
        },
    )
    body = created.json()
    # next_due_date is computed on read, not stored -- 10 days into a 30-day
    # interval means 20 days remain and nothing is overdue yet.
    assert body["next_due_date"] == (anchor + timedelta(days=30)).isoformat()
    assert body["is_overdue"] is False


async def test_a_past_due_schedule_reports_overdue(client, auth_headers):
    asset_id = await _asset(client, auth_headers)
    anchor = _today() - timedelta(days=400)
    created = await client.post(
        "/api/v1/maintenance-schedules",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "name": "Long overdue service",
            "interval_type": "time",
            "interval_days": 30,
            "anchor_date": anchor.isoformat(),
        },
    )
    assert created.json()["is_overdue"] is True


async def test_list_only_returns_this_households_schedules(client, auth_headers):
    asset_id = await _asset(client, auth_headers)
    await client.post(
        "/api/v1/maintenance-schedules",
        headers=auth_headers,
        json={"asset_id": asset_id, "name": "Tyres", "interval_type": "time", "interval_days": 180},
    )
    listing = await client.get("/api/v1/maintenance-schedules", headers=auth_headers)
    assert listing.status_code == 200
    assert [s["name"] for s in listing.json()] == ["Tyres"]


async def test_update_a_schedule(client, auth_headers):
    asset_id = await _asset(client, auth_headers)
    schedule_id = (
        await client.post(
            "/api/v1/maintenance-schedules",
            headers=auth_headers,
            json={"asset_id": asset_id, "name": "Brakes", "interval_type": "time", "interval_days": 365},
        )
    ).json()["id"]

    updated = await client.patch(
        f"/api/v1/maintenance-schedules/{schedule_id}",
        headers=auth_headers,
        json={"interval_days": 180},
    )
    assert updated.status_code == 200
    assert updated.json()["interval_days"] == 180
    assert updated.json()["name"] == "Brakes", "a partial update must not blank untouched fields"


async def test_deleted_schedule_disappears_from_reads(client, auth_headers):
    asset_id = await _asset(client, auth_headers)
    schedule_id = (
        await client.post(
            "/api/v1/maintenance-schedules",
            headers=auth_headers,
            json={"asset_id": asset_id, "name": "Coolant", "interval_type": "time", "interval_days": 365},
        )
    ).json()["id"]

    assert (
        await client.delete(f"/api/v1/maintenance-schedules/{schedule_id}", headers=auth_headers)
    ).status_code == 204

    # Soft-deleted, so it must be filtered out of both list and get.
    assert (
        await client.get(f"/api/v1/maintenance-schedules/{schedule_id}", headers=auth_headers)
    ).status_code == 404
    assert (await client.get("/api/v1/maintenance-schedules", headers=auth_headers)).json() == []


async def test_unknown_schedule_is_404(client, auth_headers):
    response = await client.get(
        f"/api/v1/maintenance-schedules/{uuid.uuid4()}", headers=auth_headers
    )
    assert response.status_code == 404


async def test_schedule_requires_an_asset_that_exists(client, auth_headers):
    response = await client.post(
        "/api/v1/maintenance-schedules",
        headers=auth_headers,
        json={
            "asset_id": str(uuid.uuid4()),
            "name": "Orphan",
            "interval_type": "time",
            "interval_days": 30,
        },
    )
    assert response.status_code == 404
