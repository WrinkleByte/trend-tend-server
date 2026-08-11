from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import SyncedEntityMixin


class StorageBackendType(StrEnum):
    LOCAL_DISK = "local_disk"
    S3 = "s3"


class Attachment(SyncedEntityMixin, Base):
    """Metadata row for a photo/receipt attachment. Blob bytes never travel
    through the row-sync JSON payload — only this metadata syncs there; bytes
    sync via a separate content-addressed transfer keyed by sha256 (see
    docs/architecture.md Section 3). Content-addressed + immutable means
    there's no conflict case for blob bytes, ever — only this metadata row
    (e.g. its deleted_at) goes through normal conflict handling."""

    __tablename__ = "attachments"

    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_backend: Mapped[StorageBackendType] = mapped_column(String(20), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    thumbnail_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
