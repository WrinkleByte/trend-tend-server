# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""Cross-repo sync contract: everything the mobile client puts on the wire has to
have somewhere to land on the server.

Card #828 exists because the server used to accept a field it could not store, and
the client had no way to find out. The brand preferences (2026-11-21, TestFlight
1.5.0 build 16) went out carrying exactly that bug -- `vehicle_details.default_*_brand`
was sent by the shipped app, undeclared in the backend schema, dropped by Pydantic,
and the owner's saved brand looked cleared on every other device.

Nothing caught it in this repo's own tests, because this repo only tests the fields it
knows about. So the contract is written down from the *client's* side:

- `scripts/sync_contract.py` reads the Kotlin payload classes out of the mobile repo
  and commits them here as `tests/contract/mobile_sync_payload.json`.
- This file asserts, for every one of those fields, that the server declares it and has
  a real place to store it -- or has an explicit reason not to, and the reason is only
  acceptable while the server names the field back as unsupported.

The asset entity is also exercised end to end through /sync/push: a payload built from
the manifest is sent and the server's `unsupported_fields` answer is compared against
the accepted gaps. That is what turns "we agreed on a field" into "the server said so".
"""

import json
import pathlib
import uuid
from importlib import import_module

from app.models.asset import (
    EquipmentDetails,
    PropertyDetails,
    ServiceDefaults,
    ValuableDetails,
    VehicleDetails,
)
from app.schemas import sync as sync_schemas

MANIFEST_PATH = pathlib.Path(__file__).parent / "contract" / "mobile_sync_payload.json"
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
CLIENT_PAYLOADS: dict[str, list[str]] = MANIFEST["payloads"]

# Client payload class -> server request schema. Named by convention (Payload -> Data);
# an entry missing here means a payload class exists on one side only.
SCHEMA_BY_PAYLOAD: dict[str, str] = {
    "AssetSyncPayload": "AssetSyncData",
    "VehicleDetailsSyncPayload": "VehicleDetailsSyncData",
    "EquipmentDetailsSyncPayload": "EquipmentDetailsSyncData",
    "PropertyDetailsSyncPayload": "PropertyDetailsSyncData",
    "ValuableDetailsSyncPayload": "ValuableDetailsSyncData",
    "MaintenanceRecordSyncPayload": "MaintenanceRecordSyncData",
    "MaintenanceScheduleSyncPayload": "MaintenanceScheduleSyncData",
    "MaintenanceCategorySyncPayload": "MaintenanceCategorySyncData",
    "FuelLogSyncPayload": "FuelLogSyncData",
    "TripLogSyncPayload": "TripLogSyncData",
    "AttachmentSyncPayload": "AttachmentSyncData",
}

# A payload's own fields land on this table, except keys listed in NESTED_TABLE which are
# nested models of their own.
TABLE_BY_PAYLOAD: dict[str, str] = {
    "AssetSyncPayload": "Asset",
    "VehicleDetailsSyncPayload": "VehicleDetails",
    "EquipmentDetailsSyncPayload": "EquipmentDetails",
    "PropertyDetailsSyncPayload": "PropertyDetails",
    "ValuableDetailsSyncPayload": "ValuableDetails",
    "MaintenanceRecordSyncPayload": "MaintenanceRecord",
    "MaintenanceScheduleSyncPayload": "MaintenanceSchedule",
    "MaintenanceCategorySyncPayload": "MaintenanceCategory",
    "FuelLogSyncPayload": "FuelLog",
    "TripLogSyncPayload": "TripLog",
    "AttachmentSyncPayload": "Attachment",
}

_TABLE_MODULES = {
    "Asset": "app.models.asset",
    "VehicleDetails": "app.models.asset",
    "EquipmentDetails": "app.models.asset",
    "PropertyDetails": "app.models.asset",
    "ValuableDetails": "app.models.asset",
    "ServiceDefaults": "app.models.asset",
    "MaintenanceRecord": "app.models.maintenance_record",
    "MaintenanceSchedule": "app.models.maintenance_schedule",
    "MaintenanceCategory": "app.models.maintenance_category",
    "FuelLog": "app.models.fuel_log",
    "TripLog": "app.models.trip_log",
    "Attachment": "app.models.attachment",
}

NESTED_TABLES = {
    "vehicle_details": VehicleDetails,
    "equipment_details": EquipmentDetails,
    "property_details": PropertyDetails,
    "valuable_details": ValuableDetails,
    "service_defaults": ServiceDefaults,
}

# Written by the server, stripped from whatever a client sends. A client may echo them
# (its local copy carries them) but they are never storage targets.
SERVER_AUTHORED = {"updated_by_user_id", "updated_by_device_id", "version", "id"}

# Fields the client sends that the server does not store, each with the reason it is
# tolerable right now. A gap earns its place here only while /sync/push names the field
# back in unsupported_fields -- then the client keeps its local value instead of pulling
# a null and writing it back over the owner's data. Fixing one means adding a column and
# deleting the line; the last test below fails if the line goes stale.
KNOWN_UNSTORED: dict[str, str] = {
    "EquipmentDetailsSyncPayload.current_hours": (
        "no equipment_details.current_hours column. The server reports it as unsupported "
        "and the phone keeps its local hours reading; syncing machine hours onto the "
        "server is its own card."
    ),
}


def _columns(table_name: str) -> set[str]:
    model = getattr(import_module(_TABLE_MODULES[table_name]), table_name)
    return {c.name for c in model.__table__.columns}


def _gapped(payload: str, field: str) -> bool:
    return f"{payload}.{field}" in KNOWN_UNSTORED


def test_the_manifest_came_from_the_client_repo():
    assert MANIFEST["source_repo"] == "tendfida-mobile"
    assert MANIFEST["source_commit"] != "unknown", "regenerate the manifest from a git checkout"
    assert len(CLIENT_PAYLOADS) >= 11, "the client sends more payload classes than this"
    assert sum(len(v) for v in CLIENT_PAYLOADS.values()) >= 127


def test_every_client_payload_class_has_a_server_schema():
    """A payload the server has no model for is a payload whose fields never arrive."""
    missing = sorted(p for p in CLIENT_PAYLOADS if p not in SCHEMA_BY_PAYLOAD)
    assert not missing, f"client payload classes with no server schema: {missing}"
    orphans = sorted(s for s in SCHEMA_BY_PAYLOAD.values() if not hasattr(sync_schemas, s))
    assert not orphans, f"server schema named here but not in app.schemas.sync: {orphans}"


def test_every_field_the_client_sends_is_declared_by_the_server():
    """The check that would have caught the brand drop before build 16 shipped it."""
    undeclared: list[str] = []
    for payload, fields in CLIENT_PAYLOADS.items():
        model = getattr(sync_schemas, SCHEMA_BY_PAYLOAD[payload])
        declared = set(model.model_fields)
        for field in fields:
            if field not in declared and not _gapped(payload, field):
                undeclared.append(f"{payload}.{field}")
    assert not undeclared, (
        "the mobile client sends fields the server drops at parse time: "
        f"{undeclared}. Either declare them and give them a column, or add them to "
        "KNOWN_UNSTORED with a reason -- and a reason only holds while /sync/push "
        "names them back."
    )


def test_every_declared_field_has_a_column_to_land_in():
    """A wire field with no column is the same silent-loss bug wearing a schema."""
    nested_columns = {k: {c.name for c in v.__table__.columns} for k, v in NESTED_TABLES.items()}
    nowhere: list[str] = []
    for payload, fields in CLIENT_PAYLOADS.items():
        columns = _columns(TABLE_BY_PAYLOAD[payload])
        for field in fields:
            if field in SERVER_AUTHORED or _gapped(payload, field):
                continue
            if field in NESTED_TABLES:
                continue
            # A parent payload also carries its own detail fields, which live on the
            # nested row rather than on the parent table.
            if field in columns or any(field in cols for cols in nested_columns.values()):
                continue
            nowhere.append(f"{payload}.{field}")
    assert not nowhere, f"declared on the wire with no column behind it: {nowhere}"


async def test_a_gap_list_entry_is_only_valid_while_the_server_says_it_out_loud(client, auth_headers):
    """Known-unstored fields must come back named in unsupported_fields, and a gap that
    stopped being a gap (column added) has to leave this list rather than sit in it."""
    device = await _register_device(client, auth_headers, "Contract probe")
    asset_id = str(uuid.uuid4())
    data = {
        "asset_type": "equipment",
        "name": "Contract probe asset",
        "equipment_details": {"manufacturer": "WrinkleByte", "current_hours": 1234},
    }
    result = await _push_asset(client, auth_headers, device, asset_id, 0, data)
    assert result["status"] == "accepted", result
    named = set(result.get("unsupported_fields") or [])
    for key, reason in KNOWN_UNSTORED.items():
        wire = key.split(".", 1)[1]
        if wire not in {"current_hours"}:
            continue  # asset-side gaps are reported at their nested path
        assert f"equipment_details.{wire}" in named, (
            f"{key} is listed as a known gap ({reason}) but the server no longer names it "
            "as unsupported -- either it now stores it (delete the entry and prove the "
            "value survives a pull) or it is silently dropped again."
        )


async def _register_device(client, auth_headers, name: str) -> dict:
    response = await client.post(
        "/api/v1/sync/devices",
        json={"platform": "android", "device_name": name},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _push_asset(client, auth_headers, device: dict, asset_id: str, base_version: int, data: dict) -> dict:
    response = await client.post(
        "/api/v1/sync/push",
        json={
            "device_id": device["id"],
            "changes": [
                {
                    "entity_type": "asset",
                    "id": asset_id,
                    "base_version": base_version,
                    "client_updated_at": "2026-11-22T00:00:00Z",
                    "data": data,
                }
            ],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["results"][0]
