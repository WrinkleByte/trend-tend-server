# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

from functools import lru_cache

from app.config import get_settings
from app.storage.base import StorageBackend
from app.storage.local_disk import LocalDiskStorage


@lru_cache
def get_storage_backend() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "s3":
        from app.storage.s3 import S3Storage

        return S3Storage(
            bucket=settings.storage_s3_bucket,
            endpoint_url=settings.storage_s3_endpoint_url,
            access_key=settings.storage_s3_access_key,
            secret_key=settings.storage_s3_secret_key,
        )
    return LocalDiskStorage(settings.storage_local_root)
