# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""An asset's details always match its current type over sync: changing
type drops the old type's details, and valuables' details are pulled too."""

import uuid

from sqlalchemy import select

from app.models.asset import EquipmentDetails, ValuableDetails, VehicleDetails


async def _register_device(client, auth_headers, name: str) -> str:
    response = await client.post(
        "/api/v1/sync/devices",
        headers=auth_headers,
        json={"platform": "ios", "device_name": name},
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


async def _push_asset(
    client, auth_headers, device_id: str, asset_id: str, base_version: int, data: dict
) -> dict:
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
                    "client_updated_at": "2026-11-16T00:00:00Z",
                    "data": data,
                }
            ],
        },
    )
    result = response.json()["results"][0]
    assert result["status"] == "accepted", result
    return result


async def _pull_asset(client, auth_headers, device_id: str, asset_id: str) -> dict:
    response = await client.post(
        "/api/v1/sync/pull",
        headers=auth_headers,
        json={"cursor": None, "device_id": device_id},
    )
    return {c["id"]: c for c in response.json()["changes"]}[asset_id]["data"]


async def test_changing_type_drops_the_old_types_details(
    client, auth_headers, db_session
):
    device = await _register_device(client, auth_headers, "Phone")
    other = await _register_device(client, auth_headers, "Tablet")
    asset_id = str(uuid.uuid4())

    first = await _push_asset(
        client,
        auth_headers,
        device,
        asset_id,
        0,
        {
            "asset_type": "equipment",
            "name": "Mower",
            "equipment_details": {"manufacturer": "Toro"},
        },
    )
    second = await _push_asset(
        client,
        auth_headers,
        device,
        asset_id,
        first["new_version"],
        {
            "asset_type": "vehicle",
            "name": "Mower",
            "vehicle_details": {"make": "Oops", "current_mileage": 5},
        },
    )
    await _push_asset(
        client,
        auth_headers,
        device,
        asset_id,
        second["new_version"],
        {
            "asset_type": "equipment",
            "name": "Mower",
            "equipment_details": {
                "manufacturer": "Toro",
                "model_number": "Recycler 22",
            },
        },
    )

    data = await _pull_asset(client, auth_headers, other, asset_id)
    assert data["asset_type"] == "equipment"
    assert data["vehicle_details"] is None
    assert data["equipment_details"]["model_number"] == "Recycler 22"

    aid = uuid.UUID(asset_id)
    assert (
        await db_session.execute(
            select(VehicleDetails).where(VehicleDetails.asset_id == aid)
        )
    ).first() is None
    assert (
        await db_session.execute(
            select(EquipmentDetails).where(EquipmentDetails.asset_id == aid)
        )
    ).first()


async def test_a_left_over_row_of_another_type_is_never_pulled(
    client, auth_headers, db_session
):
    """Rows left behind by a type change before this fix stay in the
    database; pull must ignore them rather than serve them as current."""
    device = await _register_device(client, auth_headers, "Phone")
    other = await _register_device(client, auth_headers, "Tablet")
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
            "vehicle_details": {"make": "Ford", "current_mileage": 1000},
        },
    )
    db_session.add(EquipmentDetails(asset_id=uuid.UUID(asset_id), manufacturer="Stale"))
    await db_session.commit()

    data = await _pull_asset(client, auth_headers, other, asset_id)
    assert data["vehicle_details"]["make"] == "Ford"
    assert data["equipment_details"] is None


async def test_valuable_details_are_pulled(client, auth_headers, db_session):
    device = await _register_device(client, auth_headers, "Phone")
    other = await _register_device(client, auth_headers, "Tablet")
    asset_id = str(uuid.uuid4())
    await _push_asset(
        client,
        auth_headers,
        device,
        asset_id,
        0,
        {
            "asset_type": "valuable",
            "name": "Camera",
            "valuable_details": {
                "manufacturer": "Canon",
                "serial_number": "SN1",
                "warranty_expiration": "2027-05-01",
            },
        },
    )
    assert (
        await db_session.execute(
            select(ValuableDetails).where(
                ValuableDetails.asset_id == uuid.UUID(asset_id)
            )
        )
    ).first()

    data = await _pull_asset(client, auth_headers, other, asset_id)
    assert data["valuable_details"]["serial_number"] == "SN1"
    assert data["valuable_details"]["warranty_expiration"] == "2027-05-01"
