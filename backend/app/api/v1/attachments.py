import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal, household_scoped_query
from app.db.session import get_db
from app.models.attachment import Attachment, StorageBackendType
from app.models.maintenance_record import MaintenanceRecord, RecordAttachment
from app.models.mixins import utcnow
from app.schemas.attachment import AttachmentResponse
from app.storage.base import StorageBackend
from app.storage.factory import get_storage_backend

router = APIRouter(prefix="/attachments", tags=["attachments"])


async def _get_owned_record(db: AsyncSession, principal: Principal, record_id: uuid.UUID) -> MaintenanceRecord:
    query = household_scoped_query(MaintenanceRecord, principal).where(MaintenanceRecord.id == record_id)
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Maintenance record not found")
    return record


async def _get_owned_attachment(db: AsyncSession, principal: Principal, attachment_id: uuid.UUID) -> Attachment:
    query = household_scoped_query(Attachment, principal).where(Attachment.id == attachment_id)
    result = await db.execute(query)
    attachment = result.scalar_one_or_none()
    if attachment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    return attachment


def _to_response(attachment: Attachment, storage: StorageBackend) -> AttachmentResponse:
    return AttachmentResponse.model_validate(
        {**attachment.__dict__, "url": storage.url_for(attachment.storage_key)}
    )


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile,
    record_id: uuid.UUID | None = None,
    captured_at: datetime | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> AttachmentResponse:
    if record_id is not None:
        await _get_owned_record(db, principal, record_id)

    data = await file.read()
    attachment_id = uuid.uuid4()
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

    await db.commit()
    await db.refresh(attachment)
    return _to_response(attachment, storage)


@router.get("", response_model=list[AttachmentResponse])
async def list_attachments_for_record(
    record_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> list[AttachmentResponse]:
    await _get_owned_record(db, principal, record_id)
    query = (
        household_scoped_query(Attachment, principal)
        .join(RecordAttachment, RecordAttachment.attachment_id == Attachment.id)
        .where(RecordAttachment.record_id == record_id)
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
    return Response(content=data, media_type=attachment.content_type)


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
