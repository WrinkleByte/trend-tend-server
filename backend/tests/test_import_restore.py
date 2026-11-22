# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import io
import json
import zipfile


def _make_backup_zip(bundle: dict, attachments: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.json", json.dumps(bundle))
        for name, data in (attachments or {}).items():
            zf.writestr(f"attachments/{name}", data)
    return buf.getvalue()


def _minimal_bundle(**overrides) -> dict:
    bundle = {
        "exported_at": "2026-01-01T00:00:00Z",
        "assets": [
            {
                "id": "old-asset-1",
                "household_id": "old-household",
                "asset_type": "vehicle",
                "name": "Family Minivan",
                "notes": None,
                "status": "active",
                "purchase_date": None,
                "purchase_cost": None,
                "photo_attachment_id": "old-att-1",
                "version": 3,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
                "vehicle_details": {
                    "vin": None,
                    "make": "Honda",
                    "model": "Odyssey",
                    "year": 2019,
                    "license_plate": None,
                    "current_mileage": 42000,
                    "mileage_unit": "mi",
                    "fuel_type": None,
                    # Remembered specs, in the shape a backup written before the
                    # service_defaults table existed actually has them.
                    "default_oil_viscosity": "0W-20",
                    "default_oil_filter_part_number": "OL-909",
                    "default_coolant_type": "OAT",
                },
                "equipment_details": None,
                "property_details": None,
            }
        ],
        "fuel_logs": [
            {
                "id": "old-fuel-1",
                "household_id": "old-household",
                "asset_id": "old-asset-1",
                "performed_at": "2026-01-10",
                "odometer_reading": 42100,
                "gallons": 12.5,
                "cost_per_gallon": 3.5,
                "total_cost": 43.75,
                "currency": "USD",
                "is_fill_up": True,
                "mpg": 28.0,
                "octane": 87,
                "cetane": None,
                "gas_brand": "Shell",
                "location": None,
                "notes": None,
                "additive": None,
                "version": 1,
                "created_at": "2026-01-10T00:00:00Z",
                "updated_at": "2026-01-10T00:00:00Z",
            }
        ],
        "maintenance_records": [
            {
                "id": "old-record-1",
                "household_id": "old-household",
                "asset_id": "old-asset-1",
                "performed_at": "2026-01-05",
                "performed_by": "Jiffy Lube",
                "performed_by_user_id": "old-user-id",
                "category": "oil_change",
                "custom_category": None,
                "service_tags": "oil,filter",
                "description": "Routine oil change",
                "cost": 65.0,
                "currency": "USD",
                "odometer_reading": 42050,
                "schedule_id": "old-schedule-1",
                "version": 1,
                "created_at": "2026-01-05T00:00:00Z",
                "updated_at": "2026-01-05T00:00:00Z",
            }
        ],
        "maintenance_schedules": [
            {
                "id": "old-schedule-1",
                "household_id": "old-household",
                "asset_id": "old-asset-1",
                "name": "Oil Change",
                "interval_type": "usage",
                "interval_days": None,
                "interval_usage_amount": 5000,
                "usage_field": "current_mileage",
                "anchor_date": None,
                "anchor_usage_value": 37050,
                "last_completed_record_id": "old-record-1",
                "active": True,
                "dismissed_at": None,
                "version": 2,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-05T00:00:00Z",
            }
        ],
        "attachments": [
            {
                "id": "old-att-1",
                "household_id": "old-household",
                "entity_type": "asset",
                "entity_id": "old-asset-1",
                "original_filename": "minivan.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 4,
                "sha256": "irrelevant-recomputed-on-restore",
                "captured_at": None,
                "local_file_path": "Attachments/old-att-1.jpg",
                "version": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ],
    }
    bundle.update(overrides)
    return bundle


async def test_restore_seeds_empty_household_with_remapped_ids_and_photo(client, auth_headers):
    zip_bytes = _make_backup_zip(_minimal_bundle(), attachments={"old-att-1.jpg": b"fake"})

    response = await client.post(
        "/api/v1/import/restore",
        headers=auth_headers,
        files={"file": ("backup.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 201
    summary = response.json()
    assert summary == {
        "assets": 1,
        "fuel_logs": 1,
        "maintenance_records": 1,
        "maintenance_schedules": 1,
        "attachments": 1,
        "skipped_attachments": 0,
    }

    assets = (await client.get("/api/v1/assets", headers=auth_headers)).json()
    assert len(assets) == 1
    asset = assets[0]
    # Fresh id, not the backup's original "old-asset-1".
    assert asset["id"] != "old-asset-1"
    assert asset["name"] == "Family Minivan"
    assert asset["vehicle_details"]["make"] == "Honda"
    # The specs a pre-service_defaults backup remembered survive the restore. Before
    # this they were silently dropped on the floor: restore rebuilt vehicle_details
    # from nine hand-picked columns and never looked at the rest of the row.
    assert asset["vehicle_details"]["default_oil_viscosity"] == "0W-20"
    assert asset["vehicle_details"]["default_oil_filter_part_number"] == "OL-909"
    assert asset["vehicle_details"]["default_coolant_type"] == "OAT"
    assert asset["service_defaults"]["default_oil_viscosity"] == "0W-20"
    assert asset["version"] == 1
    # Photo pointer correctly remapped to the newly created attachment.
    assert asset["photo_attachment_id"] is not None

    photo = await client.get(f"/api/v1/attachments/{asset['photo_attachment_id']}", headers=auth_headers)
    assert photo.status_code == 200
    assert photo.json()["original_filename"] == "minivan.jpg"
    blob = await client.get(f"/api/v1/attachments/{asset['photo_attachment_id']}/blob", headers=auth_headers)
    assert blob.content == b"fake"

    records = (await client.get(
        "/api/v1/maintenance-records", headers=auth_headers, params={"asset_id": asset["id"]}
    )).json()
    assert len(records) == 1
    assert records[0]["schedule_id"] is not None  # remapped, not the stale "old-schedule-1"

    fuel_logs = (await client.get(
        "/api/v1/fuel-logs", headers=auth_headers, params={"asset_id": asset["id"]}
    )).json()
    assert len(fuel_logs) == 1
    assert fuel_logs[0]["gas_brand"] == "Shell"


async def test_restore_reads_service_defaults_from_the_new_bundle_shape(client, auth_headers):
    """A current-shaped bundle writes through `service_defaults`, and the legacy fields
    still in the same row are merged under it rather than overwriting it."""
    bundle = json.loads(json.dumps(_minimal_bundle()))
    row = bundle["assets"][0]
    # A newer app wrote the same spec through both halves and disagreed with the old one:
    # the explicit new key is what gets stored.
    row["service_defaults"] = {
        "default_oil_viscosity": "0W-16",
        "default_motor_oil_brand": "Valvoline",
        "default_fuel_filter_part_number": "FF-12",
        "default_hvac_filter_size": "20x25x1",
    }

    response = await client.post(
        "/api/v1/import/restore",
        headers=auth_headers,
        files={"file": ("backup.zip", _make_backup_zip(bundle), "application/zip")},
    )
    assert response.status_code == 201

    asset = (await client.get("/api/v1/assets", headers=auth_headers)).json()[0]
    saved = asset["service_defaults"]
    assert saved["default_oil_viscosity"] == "0W-16"
    assert saved["default_motor_oil_brand"] == "Valvoline"
    assert saved["default_fuel_filter_part_number"] == "FF-12"
    assert saved["default_hvac_filter_size"] == "20x25x1"
    # A field the new key left alone still comes from the backup's legacy half.
    assert saved["default_oil_filter_part_number"] == "OL-909"
    # ...and the client that never learned about this table still sees it.
    assert asset["vehicle_details"]["default_oil_filter_part_number"] == "OL-909"


async def test_restore_carries_brands_written_into_the_old_vehicle_shape(client, auth_headers):
    """The three brand fields reached the wire while the server still stored specs inside
    vehicle_details, so a backup written by that build carries default_motor_oil_brand and
    friends in vehicle_details -- not in a service_defaults key, which did not exist yet.

    Reading only the fourteen columns that predate the table restores such a backup with
    the oil viscosity and the filter part number intact and every brand gone, and nothing
    says so: the asset comes back looking saved. That is the loss this function exists to
    prevent, arriving through the newest half of the legacy shape rather than the oldest.
    """
    bundle = json.loads(json.dumps(_minimal_bundle()))
    row = bundle["assets"][0]
    row["vehicle_details"].update(
        {
            "default_motor_oil_brand": "Pennzoil",
            "default_oil_filter_brand": "K&N",
            "default_air_filter_part_number": "TA1093",
            "default_air_filter_brand": "Fram",
        }
    )

    response = await client.post(
        "/api/v1/import/restore",
        headers=auth_headers,
        files={"file": ("backup.zip", _make_backup_zip(bundle), "application/zip")},
    )
    assert response.status_code == 201, response.text

    asset = (await client.get("/api/v1/assets", headers=auth_headers)).json()[0]
    saved = asset["service_defaults"]
    assert saved["default_motor_oil_brand"] == "Pennzoil"
    assert saved["default_oil_filter_brand"] == "K&N"
    assert saved["default_air_filter_brand"] == "Fram"
    assert saved["default_air_filter_part_number"] == "TA1093"
    # The pre-brand fields still survive alongside them.
    assert saved["default_oil_viscosity"] == "0W-20"
    assert saved["default_oil_filter_part_number"] == "OL-909"
    # And an app that only ever reads vehicle_details still gets the brands back.
    assert asset["vehicle_details"]["default_motor_oil_brand"] == "Pennzoil"
    assert asset["vehicle_details"]["default_oil_filter_brand"] == "K&N"


async def test_restore_blocked_when_household_already_has_data(client, auth_headers):
    await client.post(
        "/api/v1/assets", headers=auth_headers, json={"asset_type": "equipment", "name": "Existing Mower"}
    )
    zip_bytes = _make_backup_zip(_minimal_bundle())

    response = await client.post(
        "/api/v1/import/restore",
        headers=auth_headers,
        files={"file": ("backup.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 409
    conflict = response.json()["detail"]
    assert conflict["existing_assets"] == 1


async def test_restore_with_force_overrides_the_block(client, auth_headers):
    await client.post(
        "/api/v1/assets", headers=auth_headers, json={"asset_type": "equipment", "name": "Existing Mower"}
    )
    zip_bytes = _make_backup_zip(_minimal_bundle())

    response = await client.post(
        "/api/v1/import/restore",
        headers=auth_headers,
        data={"force": "true"},
        files={"file": ("backup.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 201

    assets = (await client.get("/api/v1/assets", headers=auth_headers)).json()
    # Both the pre-existing asset and the restored one now coexist -- force
    # deliberately doesn't wipe first, matching the "loud override, not a
    # silent wipe" design.
    assert len(assets) == 2


async def test_restore_skips_attachment_kinds_backend_cant_link(client, auth_headers):
    bundle = _minimal_bundle(
        attachments=[
            {
                "id": "old-att-2",
                "household_id": "old-household",
                "entity_type": "fuel_log",
                "entity_id": "old-fuel-1",
                "original_filename": "receipt.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 4,
                "sha256": "x",
                "captured_at": None,
                "local_file_path": "Attachments/old-att-2.jpg",
                "version": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]
    )
    zip_bytes = _make_backup_zip(bundle, attachments={"old-att-2.jpg": b"fake"})

    response = await client.post(
        "/api/v1/import/restore",
        headers=auth_headers,
        files={"file": ("backup.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 201
    summary = response.json()
    assert summary["attachments"] == 0
    assert summary["skipped_attachments"] == 1


async def test_restore_without_attachment_bytes_skips_metadata_only_rows(client, auth_headers):
    # A backup made without "include attachments" still has the JSON row,
    # but no file in the archive.
    zip_bytes = _make_backup_zip(_minimal_bundle())

    response = await client.post(
        "/api/v1/import/restore",
        headers=auth_headers,
        files={"file": ("backup.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 201
    summary = response.json()
    assert summary["assets"] == 1
    assert summary["attachments"] == 0
    assert summary["skipped_attachments"] == 1

    assets = (await client.get("/api/v1/assets", headers=auth_headers)).json()
    assert assets[0]["photo_attachment_id"] is None


async def test_restore_rejects_non_zip_file(client, auth_headers):
    response = await client.post(
        "/api/v1/import/restore",
        headers=auth_headers,
        files={"file": ("backup.zip", b"not a zip", "application/zip")},
    )
    assert response.status_code == 400
