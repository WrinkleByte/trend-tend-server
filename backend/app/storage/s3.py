import asyncio

import boto3

from app.storage.base import StorageBackend


class S3Storage(StorageBackend):
    """Works against AWS S3 or any S3-compatible endpoint (MinIO, R2, B2) via
    the configurable endpoint_url — self-hosters aren't locked into AWS."""

    def __init__(self, *, bucket: str, endpoint_url: str, access_key: str, secret_key: str):
        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
        )

    async def put(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(self._client.put_object, Bucket=self.bucket, Key=key, Body=data)

    async def get(self, key: str) -> bytes:
        response = await asyncio.to_thread(self._client.get_object, Bucket=self.bucket, Key=key)
        return response["Body"].read()

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self.bucket, Key=key)

    def url_for(self, key: str) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=3600
        )
