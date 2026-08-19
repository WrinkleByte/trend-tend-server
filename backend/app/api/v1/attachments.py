import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal, household_scoped_query
from app.db.session import get_db
from app.models.asset import Asset
from app.models.attachment import Attachment, StorageBackendType
from app.models.fuel_log import FuelLog, FuelLogAttachment
from app.models.maintenance_record import MaintenanceRecord, RecordAttachment
from app.models.mixins import utcnow
from app.models.trip_log import TripLog, TripLogAttachment
from app.schemas.attachment import AttachmentResponse
from app.storage.base import StorageBackend
from app.storage.factory import get_storage_backend

router = APIRouter(prefix="/attachments", tags=["attachments"])

# Content types we're willing to hand a browser to render in-place. Anything
# not on this list is still downloadable, just forced to a non-executing
# disposition -- see _blob_response below for why that matters.
#
# Deliberately images-only, and deliberately NOT image/svg+xml: SVG is an
# XML document that can carry <script>, so rendering one inline on our own
# origin is script execution, not image display. PDF is off the list too --
# browsers sandbox their viewers, but it's an active format and nothing in
# this app needs PDFs rendered inline.
INLINE_RENDERABLE_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp", "image/heic", "image/heif"}
)

_FALLBACK_CONTENT_TYPE = "application/octet-stream"

# Upload ceiling. Receipt/odometer photos from a modern phone run 3-12MB, so
# this leaves generous headroom while bounding what a single request can
# cost us. Enforced by reading in chunks and stopping early (see
# _read_upload_capped) rather than trusting Content-Length, which a client
# controls and can simply lie about.
MAX_ATTACHMENT_BYTES = 32 * 1024 * 1024
_UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _read_upload_capped(file: UploadFile) -> bytes:
    """Read an upload into memory, refusing anything over the cap.

    The previous `await file.read()` had no bound at all: a single large
    upload could exhaust the container's memory, and the deployment runs one
    uvicorn worker (see core/rate_limit.py's docstring, which depends on
    that), so that's the whole instance rather than one process among many.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_UPLOAD_CHUNK_BYTES):
        total += len(chunk)
        if total > MAX_ATTACHMENT_BYTES:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"Attachment exceeds the {MAX_ATTACHMENT_BYTES // (1024 * 1024)}MB limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _get_owned_record(db: AsyncSession, principal: Principal, record_id: uuid.UUID) -> MaintenanceRecord:
    query = household_scoped_query(MaintenanceRecord, principal).where(MaintenanceRecord.id == record_id)
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Maintenance record not found")
    return record


async def _get_owned_fuel_log(db: AsyncSession, principal: Principal, fuel_log_id: uuid.UUID) -> FuelLog:
    query = household_scoped_query(FuelLog, principal).where(FuelLog.id == fuel_log_id)
    result = await db.execute(query)
    fuel_log = result.scalar_one_or_none()
    if fuel_log is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel log not found")
    return fuel_log


async def _get_owned_trip_log(db: AsyncSession, principal: Principal, trip_log_id: uuid.UUID) -> TripLog:
    query = household_scoped_query(TripLog, principal).where(TripLog.id == trip_log_id)
    result = await db.execute(query)
    trip_log = result.scalar_one_or_none()
    if trip_log is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip log not found")
    return trip_log


async def _get_owned_asset(db: AsyncSession, principal: Principal, asset_id: uuid.UUID) -> Asset:
    query = household_scoped_query(Asset, principal).where(Asset.id == asset_id)
    result = await db.execute(query)
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    return asset


async def _get_owned_attachment(db: AsyncSession, principal: Principal, attachment_id: uuid.UUID) -> Attachment:
    query = household_scoped_query(Attachment, principal).where(Attachment.id == attachment_id)
    result = await db.execute(query)
    attachment = result.scalar_one_or_none()
    if attachment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    return attachment


def _blob_response(data: bytes, attachment: Attachment) -> Response:
    """Serve attachment bytes without letting an upload become script on our
    own origin.

    content_type is whatever the uploading client claimed -- it is never
    sniffed or validated on the way in. Echoing it back unchecked meant a
    household member (or anyone with a stolen token) could upload an .html
    or .svg as text/html and have it execute on the API's origin when
    viewed. Since the web app is same-origin with this API and keeps its
    tokens in localStorage, that was a direct path from "can upload a file"
    to "can read another user's session".

    So: known-safe image types render inline as themselves; everything else
    is served as an opaque download. nosniff is what makes that stick --
    without it a browser may content-sniff its way back to text/html and
    execute anyway, ignoring the declared type entirely.
    """
    is_inline = attachment.content_type in INLINE_RENDERABLE_CONTENT_TYPES
    filename = attachment.original_filename or "attachment"
    # Quotes and newlines in a filename would let a crafted name inject extra
    # header directives; strip them rather than escaping.
    safe_filename = filename.replace('"', "").replace("\\", "").replace("\r", "").replace("\n", "")
    disposition = "inline" if is_inline else "attachment"
    return Response(
        content=data,
        media_type=attachment.content_type if is_inline else _FALLBACK_CONTENT_TYPE,
        headers={
            "Content-Disposition": f'{disposition}; filename="{safe_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


def _to_response(attachment: Attachment, storage: StorageBackend) -> AttachmentResponse:
    return AttachmentResponse.model_validate(
        {**attachment.__dict__, "url": storage.url_for(attachment.storage_key)}
    )


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile,
    attachment_id: uuid.UUID | None = None,
    record_id: uuid.UUID | None = None,
    fuel_log_id: uuid.UUID | None = None,
    trip_log_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    captured_at: datetime | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> AttachmentResponse:
    # A client-supplied attachment_id (mobile's sync outbox retries an
    # upload with the same locally-generated id after a dropped connection,
    # same as every other synced entity's client-generated UUID) makes
    # retries idempotent -- skip re-uploading the blob and re-linking
    # entirely, just return what's already there. Web never sends this, so
    # its behavior (server always mints a fresh id) is unchanged.
    if attachment_id is not None:
        existing = await db.execute(
            household_scoped_query(Attachment, principal).where(Attachment.id == attachment_id)
        )
        existing_attachment = existing.scalar_one_or_none()
        if existing_attachment is not None:
            return _to_response(existing_attachment, storage)

        # id is a global primary key, not household-scoped, so a collision
        # with another household's attachment (deliberate or a genuine
        # UUID clash) can't just fall through to the insert below -- that
        # would surface as an unhandled 500 (unique constraint violation)
        # rather than a clean error, and do it *after* already writing the
        # blob to storage. Check existence globally, without touching any
        # of that row's data, so nothing about the other household leaks.
        collision = await db.execute(select(Attachment.id).where(Attachment.id == attachment_id))
        if collision.scalar_one_or_none() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "attachment_id already in use")

    if record_id is not None:
        await _get_owned_record(db, principal, record_id)
    if fuel_log_id is not None:
        await _get_owned_fuel_log(db, principal, fuel_log_id)
    if trip_log_id is not None:
        await _get_owned_trip_log(db, principal, trip_log_id)
    asset: Asset | None = None
    if asset_id is not None:
        # A profile photo is 1:1 with its asset (a direct FK column, not a
        # join table like RecordAttachment) -- fetched up front so its
        # previous photo_attachment_id is on hand once the new attachment
        # exists, same "old id captured before the new row lands" shape
        # every other update in this codebase uses.
        asset = await _get_owned_asset(db, principal, asset_id)
    previous_photo_attachment_id = asset.photo_attachment_id if asset is not None else None

    data = await _read_upload_capped(file)
    attachment_id = attachment_id or uuid.uuid4()
    storage_key = f"{principal.household_id}/{attachment_id}/{file.filename}"
    await storage.put(storage_key, data)

    attachment = Attachment(
        id=attachment_id,
        household_id=principal.household_id,
        updated_by_device_id=principal.device_id,
        original_filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        storage_backend=StorageBackendType.LOCAL_DISK
        if storage.__class__.__name__ == "LocalDiskStorage"
        else StorageBackendType.S3,
        storage_key=storage_key,
        sha256=hashlib.sha256(data).hexdigest(),
        captured_at=captured_at,
    )
    db.add(attachment)
    await db.flush()

    if record_id is not None:
        db.add(RecordAttachment(id=uuid.uuid4(), record_id=record_id, attachment_id=attachment.id))
    if fuel_log_id is not None:
        db.add(FuelLogAttachment(id=uuid.uuid4(), fuel_log_id=fuel_log_id, attachment_id=attachment.id))
    if trip_log_id is not None:
        db.add(TripLogAttachment(id=uuid.uuid4(), trip_log_id=trip_log_id, attachment_id=attachment.id))
    if asset is not None:
        asset.photo_attachment_id = attachment.id
        asset.updated_by_device_id = principal.device_id
        asset.version += 1
        asset.updated_at = utcnow()
        if previous_photo_attachment_id is not None:
            # Same soft-delete-metadata-only tradeoff as delete_attachment
            # below -- the old blob is left in place rather than adding
            # cascade-delete logic.
            prev_result = await db.execute(
                select(Attachment).where(Attachment.id == previous_photo_attachment_id)
            )
            previous_attachment = prev_result.scalar_one_or_none()
            if previous_attachment is not None:
                previous_attachment.deleted_at = utcnow()
                previous_attachment.updated_by_device_id = principal.device_id
                previous_attachment.version += 1

    await db.commit()
    await db.refresh(attachment)
    return _to_response(attachment, storage)


@router.get("", response_model=list[AttachmentResponse])
async def list_attachments(
    record_id: uuid.UUID | None = None,
    fuel_log_id: uuid.UUID | None = None,
    trip_log_id: uuid.UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> list[AttachmentResponse]:
    provided = [x for x in (record_id, fuel_log_id, trip_log_id) if x is not None]
    if len(provided) != 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Exactly one of record_id, fuel_log_id, trip_log_id is required"
        )

    if record_id is not None:
        await _get_owned_record(db, principal, record_id)
        query = (
            household_scoped_query(Attachment, principal)
            .join(RecordAttachment, RecordAttachment.attachment_id == Attachment.id)
            .where(RecordAttachment.record_id == record_id)
        )
    elif fuel_log_id is not None:
        await _get_owned_fuel_log(db, principal, fuel_log_id)
        query = (
            household_scoped_query(Attachment, principal)
            .join(FuelLogAttachment, FuelLogAttachment.attachment_id == Attachment.id)
            .where(FuelLogAttachment.fuel_log_id == fuel_log_id)
        )
    else:
        await _get_owned_trip_log(db, principal, trip_log_id)
        query = (
            household_scoped_query(Attachment, principal)
            .join(TripLogAttachment, TripLogAttachment.attachment_id == Attachment.id)
            .where(TripLogAttachment.trip_log_id == trip_log_id)
        )

    result = await db.execute(query)
    return [_to_response(a, storage) for a in result.scalars().all()]


@router.get("/{attachment_id}", response_model=AttachmentResponse)
async def get_attachment(
    attachment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> AttachmentResponse:
    attachment = await _get_owned_attachment(db, principal, attachment_id)
    return _to_response(attachment, storage)


@router.get("/{attachment_id}/blob")
async def get_attachment_blob(
    attachment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> Response:
    attachment = await _get_owned_attachment(db, principal, attachment_id)
    if attachment.storage_backend == StorageBackendType.S3:
        return RedirectResponse(storage.url_for(attachment.storage_key))
    data = await storage.get(attachment.storage_key)
    return _blob_response(data, attachment)


@router.post("/{attachment_id}/link/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def link_attachment(
    attachment_id: uuid.UUID,
    record_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _get_owned_attachment(db, principal, attachment_id)
    await _get_owned_record(db, principal, record_id)
    db.add(RecordAttachment(id=uuid.uuid4(), record_id=record_id, attachment_id=attachment_id))
    await db.commit()


@router.delete("/{attachment_id}/link/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_attachment(
    attachment_id: uuid.UUID,
    record_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    # Both sides are ownership-checked before the delete, exactly as
    # link_attachment above does. Without these, the delete below is filtered
    # only on the two path UUIDs -- nothing scopes it to the caller's
    # household -- so anyone who knew (or brute-forced) a pair of ids could
    # sever another household's attachment link. Same bug class as the
    # cross-household FK injection in Vikunja #32; missed by that sweep
    # because #32 targeted create/update paths and this is a delete.
    await _get_owned_attachment(db, principal, attachment_id)
    await _get_owned_record(db, principal, record_id)
    await db.execute(
        RecordAttachment.__table__.delete().where(
            RecordAttachment.attachment_id == attachment_id, RecordAttachment.record_id == record_id
        )
    )
    await db.commit()


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    attachment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    # Soft-delete the metadata row only, same as every other synced entity —
    # the blob is left in place (an accepted, bounded storage leak) rather
    # than adding cascade-delete/reference-counting logic. See
    # docs/architecture.md Section 5 (mobile attachment) for the identical
    # tradeoff already made there.
    attachment = await _get_owned_attachment(db, principal, attachment_id)
    attachment.deleted_at = utcnow()
    attachment.updated_by_device_id = principal.device_id
    attachment.version += 1
    await db.commit()
