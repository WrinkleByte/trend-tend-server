import asyncio
from pathlib import Path

from app.storage.base import StorageBackend


class LocalDiskStorage(StorageBackend):
    def __init__(self, root_path: str):
        self.root = Path(root_path)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise ValueError(f"storage key escapes root: {key!r}")
        return path

    async def put(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path_for(key).read_bytes)

    async def delete(self, key: str) -> None:
        path = self._path_for(key)
        if path.exists():
            await asyncio.to_thread(path.unlink)

    def url_for(self, key: str) -> str:
        return f"/api/v1/attachments/blob/{key}"
