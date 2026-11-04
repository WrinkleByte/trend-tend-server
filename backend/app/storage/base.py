# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Attachment blob storage abstraction. The backend decides which
    implementation is active (via config) and tells clients which upload path
    to use in its API responses — clients never need per-deployment
    configuration of their own. See docs/architecture.md Section 2."""

    @abstractmethod
    async def put(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    def url_for(self, key: str) -> str:
        """A URL the client can GET the blob from — a locally-served static
        path for local_disk, or a pre-signed URL for s3."""
        ...
