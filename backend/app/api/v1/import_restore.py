import hashlib
import io
import json
import uuid
import zipfile
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal, household_scoped_query
from app.db.session import get_db
from app.models.asset import Asset, EquipmentDetails, PropertyDetails, VehicleDetails
from app.models.attachment import Attachment, StorageBackendType
from app.models.fuel_log import FuelLog
from app.models.maintenance_record import MaintenanceRecord, RecordAttachment
from app.models.maintenance_schedule import MaintenanceSchedule
from app.schemas.import_restore import RestoreConflict, RestoreSummary
from app.storage.base import StorageBackend
from app.storage.factory import get_storage_backend

router = APIRouter(prefix="/import", tags=["import"])

# Backend attachments only ever link to a maintenance_record (RecordAttachment
# join table) or an asset's profile photo (Asset.photo_attachment_id) -- no
# fuel_log/trip_log equivalent exists server-side (see RecordAttachment's doc
# comment in maintenance_record.py). A restored backup containing those kinds
# has nowhere to put them; they're counted as skipped, not silently dropped.
_RESTORABLE_ATTACHMENT_KINDS = {"asset", "maintenance_record"}


def _parse_date(value: str | None):
    return datetime.fromisoformat(value).date() if value else None


def _parse_datetime(value: str | None):
    return datetime.fromisoformat(value) if value else None


def _parse_decimal(value: Any) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


async def _existing_counts(db: AsyncSession, principal: Principal) -> dict[str, int]:
    counts = {}
    for label, model in (
        ("existing_assets", Asset),
        ("existing_fuel_logs", FuelLog),
        ("existing_maintenance_records", MaintenanceRecord),
        ("existing_maintenance_schedules", MaintenanceSchedule),
    ):
        result = await db.execute(select(func.count()).select_from(household_scoped_query(model, principal).subquery()))
        counts[label] = result.scalar_one()
    return counts


@router.post("/restore", response_model=RestoreSummary, status_code=status.HTTP_201_CREATED)
async def restore_backup(
    file: UploadFile,
    force: bool = Form(False),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> RestoreSummary:
    """Seeds the caller's household from a backup zip produced by any
    platform's export feature (JSON + an attachments/ folder, each file
    named <attachment id>.<ext> -- see AttachmentExportRow's doc comment in
    the mobile shared module for why). Every restored row gets a freshly
    generated id; nothing from the backup's own ids/household_id is reused,
    so this can never collide with data that already exists anywhere --
    deliberately a "seed a blank slate" operation, not a merge. Blocked by
    default if the household already has any data (see RestoreConflict);
    force=true overrides that, for the "wipe and reseed" case.

    Intentionally NOT how a paired household should recover a lost device
    -- that's what re-pairing + a normal sync pull already does safely,
    since the server is the durable copy. This exists for standalone
    mobile installs and for the truly-lost-everything disaster case.
    """
    if not force:
        existing = await _existing_counts(db, principal)
        if any(existing.values()):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=RestoreConflict(**existing).model_dump(),
            )

    raw = await file.read()
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
        bundle = json.loads(archive.read("data.json"))
    except (zipfile.BadZipFile, KeyError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a valid backup zip (missing data.json)") from exc

    attachment_files: dict[str, bytes] = {}
    for name in archive.namelist():
        if name.startswith("attachments/") and not name.endswith("/"):
            stem = name.removeprefix("attachments/").rsplit(".", 1)[0]
            attachment_files[stem] = archive.read(name)

    asset_id_map = {row["id"]: uuid.uuid4() for row in bundle.get("assets", [])}
    record_id_map = {row["id"]: uuid.uuid4() for row in bundle.get("maintenance_records", [])}
    schedule_id_map = {row["id"]: uuid.uuid4() for row in bundle.get("maintenance_schedules", [])}
    fuel_log_id_map = {row["id"]: uuid.uuid4() for row in bundle.get("fuel_logs", [])}
    attachment_id_map = {row["id"]: uuid.uuid4() for row in bundle.get("attachments", [])}

    # 1. Assets (+ type-specific detail rows). photo_attachment_id is
    # patched in later, once attachments exist to point at.
    for row in bundle.get("assets", []):
        new_id = asset_id_map[row["id"]]
        db.add(
            Asset(
                id=new_id,
                household_id=principal.household_id,
                asset_type=row["asset_type"],
                name=row["name"],
                notes=row.get("notes"),
                status=row.get("status", "active"),
                purchase_date=_parse_date(row.get("purchase_date")),
                purchase_cost=_parse_decimal(row.get("purchase_cost")),
                version=1,
                created_at=_parse_datetime(row["created_at"]),
                updated_at=_parse_datetime(row["updated_at"]),
            )
        )
        if row.get("vehicle_details"):
            vd = row["vehicle_details"]
            db.add(
                VehicleDetails(
                    asset_id=new_id,
                    vin=vd.get("vin"),
                    make=vd.get("make"),
                    model=vd.get("model"),
                    year=vd.get("year"),
                    license_plate=vd.get("license_plate"),
                    current_mileage=vd.get("current_mileage"),
                    mileage_unit=vd.get("mileage_unit", "mi"),
                    fuel_type=vd.get("fuel_type"),
                )
            )
        if row.get("equipment_details"):
            ed = row["equipment_details"]
            db.add(
                EquipmentDetails(
                    asset_id=new_id,
                    manufacturer=ed.get("manufacturer"),
                    model_number=ed.get("model_number"),
                    serial_number=ed.get("serial_number"),
                    warranty_expiration=_parse_date(ed.get("warranty_expiration")),
                )
            )
        if row.get("property_details"):
            pd = row["property_details"]
            db.add(
                PropertyDetails(
                    asset_id=new_id,
                    address=pd.get("address"),
                    # A parent asset from the SAME backup remaps; one that
                    # isn't in this backup at all (shouldn't happen for a
                    # self-consistent export, but not assumed) is dropped
                    # rather than left dangling at a stale, meaningless id.
                    parent_asset_id=asset_id_map.get(pd["parent_asset_id"]) if pd.get("parent_asset_id") else None,
                    install_date=_parse_date(pd.get("install_date")),
                )
            )
    await db.flush()

    # 2. Maintenance records (schedule_id patched in step 4, once schedules
    # exist -- MaintenanceSchedule.last_completed_record_id and
    # MaintenanceRecord.schedule_id reference each other).
    records_by_new_id: dict[uuid.UUID, MaintenanceRecord] = {}
    for row in bundle.get("maintenance_records", []):
        new_id = record_id_map[row["id"]]
        record = MaintenanceRecord(
            id=new_id,
            household_id=principal.household_id,
            asset_id=asset_id_map[row["asset_id"]],
            performed_at=_parse_date(row["performed_at"]),
            performed_by=row.get("performed_by"),
            # Not remapped: a user id from the backup's original household
            # has no meaning (or worse, an unintended meaning) in this one.
            performed_by_user_id=None,
            category=row["category"],
            custom_category=row.get("custom_category"),
            # service_tags exists on mobile's schema only -- no backend
            # column to restore it into (see MaintenanceRecordExportRow's
            # doc comment in the mobile shared module).
            description=row.get("description"),
            cost=_parse_decimal(row.get("cost")),
            currency=row.get("currency", "USD"),
            odometer_reading=row.get("odometer_reading"),
            version=1,
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )
        db.add(record)
        records_by_new_id[new_id] = record
    await db.flush()

    # 3. Maintenance schedules -- asset_id and last_completed_record_id both
    # resolvable now (assets and records already exist).
    for row in bundle.get("maintenance_schedules", []):
        db.add(
            MaintenanceSchedule(
                id=schedule_id_map[row["id"]],
                household_id=principal.household_id,
                asset_id=asset_id_map[row["asset_id"]],
                name=row["name"],
                interval_type=row["interval_type"],
                interval_days=row.get("interval_days"),
                interval_usage_amount=row.get("interval_usage_amount"),
                usage_field=row.get("usage_field"),
                anchor_date=_parse_date(row.get("anchor_date")),
                anchor_usage_value=row.get("anchor_usage_value"),
                last_completed_record_id=record_id_map.get(row["last_completed_record_id"])
                if row.get("last_completed_record_id")
                else None,
                active=row.get("active", True),
                # dismissed_at is mobile-only bookkeeping (see
                # MaintenanceScheduleExportRow's doc comment) -- no backend
                # column.
                version=1,
                created_at=_parse_datetime(row["created_at"]),
                updated_at=_parse_datetime(row["updated_at"]),
            )
        )
    await db.flush()

    # 4. Patch schedule_id back onto records now that schedules exist.
    for row in bundle.get("maintenance_records", []):
        if row.get("schedule_id"):
            records_by_new_id[record_id_map[row["id"]]].schedule_id = schedule_id_map.get(row["schedule_id"])

    # 5. Fuel logs -- no cross-references besides asset_id.
    for row in bundle.get("fuel_logs", []):
        db.add(
            FuelLog(
                id=fuel_log_id_map[row["id"]],
                household_id=principal.household_id,
                asset_id=asset_id_map[row["asset_id"]],
                performed_at=_parse_date(row["performed_at"]),
                odometer_reading=row.get("odometer_reading"),
                gallons=_parse_decimal(row["gallons"]),
                cost_per_gallon=_parse_decimal(row.get("cost_per_gallon")),
                total_cost=_parse_decimal(row.get("total_cost")),
                currency=row.get("currency", "USD"),
                is_fill_up=row.get("is_fill_up", True),
                mpg=_parse_decimal(row.get("mpg")),
                octane=row.get("octane"),
                cetane=row.get("cetane"),
                gas_brand=row.get("gas_brand"),
                location=row.get("location"),
                notes=row.get("notes"),
                additive=row.get("additive"),
                version=1,
                created_at=_parse_datetime(row["created_at"]),
                updated_at=_parse_datetime(row["updated_at"]),
            )
        )

    # 6. Attachments -- upload each file's bytes to this deployment's own
    # storage backend (never trusts the backup's storage_key/backend, which
    # point at wherever the backup originally came from) and link it to its
    # already-remapped entity.
    restored_attachment_count = 0
    skipped_attachment_count = 0
    asset_photo_patches: dict[uuid.UUID, uuid.UUID] = {}
    for row in bundle.get("attachments", []):
        entity_type = row["entity_type"]
        if entity_type not in _RESTORABLE_ATTACHMENT_KINDS:
            skipped_attachment_count += 1
            continue
        data = attachment_files.get(row["id"])
        if data is None:
            # JSON row present but no matching file in the archive -- the
            # backup was made without "include attachments"; skip quietly,
            # the row's data.json entry is metadata-only in that case.
            skipped_attachment_count += 1
            continue

        new_attachment_id = attachment_id_map[row["id"]]
        storage_key = f"{principal.household_id}/{new_attachment_id}/{row['original_filename']}"
        await storage.put(storage_key, data)
        db.add(
            Attachment(
                id=new_attachment_id,
                household_id=principal.household_id,
                original_filename=row["original_filename"],
                content_type=row["content_type"],
                size_bytes=len(data),
                storage_backend=StorageBackendType.LOCAL_DISK
                if storage.__class__.__name__ == "LocalDiskStorage"
                else StorageBackendType.S3,
                storage_key=storage_key,
                # Recomputed from the actual restored bytes rather than
                # trusted from the backup -- matches upload_attachment's own
                # behavior, and catches any transport corruption.
                sha256=hashlib.sha256(data).hexdigest(),
                captured_at=_parse_datetime(row.get("captured_at")),
                version=1,
                created_at=_parse_datetime(row["created_at"]),
                updated_at=_parse_datetime(row["updated_at"]),
            )
        )
        restored_attachment_count += 1

        if entity_type == "asset":
            asset_photo_patches[asset_id_map[row["entity_id"]]] = new_attachment_id
        elif entity_type == "maintenance_record":
            db.add(
                RecordAttachment(
                    id=uuid.uuid4(),
                    record_id=record_id_map[row["entity_id"]],
                    attachment_id=new_attachment_id,
                )
            )
    await db.flush()

    # 7. Patch asset photo pointers now that attachments exist.
    if asset_photo_patches:
        result = await db.execute(select(Asset).where(Asset.id.in_(asset_photo_patches.keys())))
        for asset in result.scalars().all():
            asset.photo_attachment_id = asset_photo_patches[asset.id]

    await db.commit()

    return RestoreSummary(
        assets=len(asset_id_map),
        fuel_logs=len(fuel_log_id_map),
        maintenance_records=len(record_id_map),
        maintenance_schedules=len(schedule_id_map),
        attachments=restored_attachment_count,
        skipped_attachments=skipped_attachment_count,
    )
