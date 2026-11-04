# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

from sqlalchemy import select

from app.models.api_token import ApiToken
from app.models.asset import Asset, VehicleDetails
from app.models.fuel_log import FuelLog
from app.models.household import Household, HouseholdMembership
from app.models.maintenance_record import MaintenanceRecord
from app.models.maintenance_schedule import MaintenanceSchedule
from app.models.trip_log import TripLog


async def _register(client, email: str, household_name: str) -> dict:
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


def _headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _populate_household(client, headers: dict) -> str:
    """Creates one of everything a household can hold, so a wipe has
    something real to clean up. Returns the asset id."""
    asset_response = await client.post(
        "/api/v1/assets",
        headers=headers,
        json={"asset_type": "vehicle", "name": "Family Minivan", "vehicle_details": {"current_mileage": 41500}},
    )
    asset_id = asset_response.json()["id"]

    await client.post(
        "/api/v1/fuel-logs",
        headers=headers,
        json={"asset_id": asset_id, "performed_at": "2026-01-15", "odometer_reading": 41800, "gallons": "12.5"},
    )
    await client.post(
        "/api/v1/trip-logs",
        headers=headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-01-15T09:00:00Z",
            "purpose": "business",
            "start_odometer": "41500.0",
            "end_odometer": "41550.0",
            "distance": "50.0",
        },
    )
    schedule_response = await client.post(
        "/api/v1/maintenance-schedules",
        headers=headers,
        json={"asset_id": asset_id, "name": "Oil change", "interval_type": "time", "interval_days": 180},
    )
    schedule_id = schedule_response.json()["id"]
    await client.post(
        "/api/v1/maintenance-records",
        headers=headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-01-15",
            "category": "oil_change",
            "schedule_id": schedule_id,
        },
    )
    await client.post("/api/v1/api-tokens", headers=headers, json={"name": "Test device"})

    return asset_id


async def test_wipe_household_requires_owner(client):
    alice = await _register(client, "alice@example.com", "Alice's House")
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=_headers(alice), json={"invited_email": "bob@example.com"}
        )
    ).json()
    bob_tokens = await _register(client, "bob@example.com", "irrelevant, joins Alice's House below")
    accept = await client.post(
        "/api/v1/households/invites/accept", headers=_headers(bob_tokens), json={"token": invite["token"]}
    )
    bob_in_alice_house = _headers(accept.json())

    response = await client.post("/api/v1/households/me/wipe-data", headers=bob_in_alice_house)
    assert response.status_code == 403


async def test_wipe_household_clears_data_but_keeps_household(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    headers = _headers(alice)
    asset_id = await _populate_household(client, headers)

    household_row = (await db_session.execute(select(Household))).scalars().one()
    household_id = household_row.id

    response = await client.post("/api/v1/households/me/wipe-data", headers=headers)
    assert response.status_code == 204

    # Data rows are soft-deleted, not gone entirely — mobile sync needs the
    # tombstone (deleted_at) to know to clear its own local copy; a hard
    # delete here would be invisible to a paired device that's still
    # connected to this same (surviving) household.
    asset = (await db_session.execute(select(Asset).where(Asset.id == asset_id))).scalar_one()
    assert asset.deleted_at is not None
    assert asset.version == 2

    # The non-synced detail child row can be hard-deleted immediately —
    # it's never independently synced, only ever read alongside its parent.
    assert (
        await db_session.execute(select(VehicleDetails).where(VehicleDetails.asset_id == asset_id))
    ).scalar_one_or_none() is None

    fuel_log = (await db_session.execute(select(FuelLog).where(FuelLog.household_id == household_id))).scalar_one()
    assert fuel_log.deleted_at is not None
    trip_log = (await db_session.execute(select(TripLog).where(TripLog.household_id == household_id))).scalar_one()
    assert trip_log.deleted_at is not None
    schedule = (
        await db_session.execute(select(MaintenanceSchedule).where(MaintenanceSchedule.household_id == household_id))
    ).scalar_one()
    assert schedule.deleted_at is not None
    record = (
        await db_session.execute(select(MaintenanceRecord).where(MaintenanceRecord.household_id == household_id))
    ).scalar_one()
    assert record.deleted_at is not None

    # The API surface (what clients actually see) reports nothing left.
    assets_after = await client.get("/api/v1/assets", headers=headers)
    assert assets_after.json() == []

    # But the household, its membership, and its API token all survive.
    assert (
        await db_session.execute(select(Household).where(Household.id == household_id))
    ).scalar_one_or_none() is not None
    assert (
        await db_session.execute(
            select(HouseholdMembership).where(HouseholdMembership.household_id == household_id)
        )
    ).scalar_one_or_none() is not None
    assert (
        await db_session.execute(select(ApiToken).where(ApiToken.household_id == household_id))
    ).scalar_one_or_none() is not None


async def test_wiped_household_owner_session_still_works(client):
    alice = await _register(client, "alice@example.com", "Alice's House")
    headers = _headers(alice)
    await _populate_household(client, headers)

    response = await client.post("/api/v1/households/me/wipe-data", headers=headers)
    assert response.status_code == 204

    # Unlike delete, the session is still valid — same household, just empty.
    check = await client.get("/api/v1/assets", headers=headers)
    assert check.status_code == 200
    assert check.json() == []


async def test_wipe_household_does_not_affect_other_households(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    bob = await _register(client, "bob@example.com", "Bob's House")
    bob_asset = await client.post(
        "/api/v1/assets", headers=_headers(bob), json={"asset_type": "equipment", "name": "Mower"}
    )
    bob_asset_id = bob_asset.json()["id"]

    response = await client.post("/api/v1/households/me/wipe-data", headers=_headers(alice))
    assert response.status_code == 204

    assert (await db_session.execute(select(Asset).where(Asset.id == bob_asset_id))).scalar_one_or_none() is not None
    bob_check = await client.get("/api/v1/assets", headers=_headers(bob))
    assert bob_check.status_code == 200
    assert len(bob_check.json()) == 1
