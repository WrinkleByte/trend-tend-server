import uuid


async def _create_record(client, auth_headers) -> str:
    asset = await client.post(
        "/api/v1/assets", headers=auth_headers, json={"asset_type": "equipment", "name": "Snow Blower"}
    )
    asset_id = asset.json()["id"]
    record = await client.post(
        "/api/v1/maintenance-records",
        headers=auth_headers,
        json={"asset_id": asset_id, "performed_at": "2026-01-15", "category": "repair"},
    )
    return record.json()["id"]


async def test_upload_attachment_linked_to_record(client, auth_headers):
    record_id = await _create_record(client, auth_headers)

    response = await client.post(
        "/api/v1/attachments",
        headers=auth_headers,
        params={"record_id": record_id},
        files={"file": ("receipt.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert response.status_code == 201
    attachment = response.json()
    assert attachment["original_filename"] == "receipt.jpg"
    assert attachment["content_type"] == "image/jpeg"
    assert attachment["size_bytes"] == len(b"fake-jpeg-bytes")
    assert attachment["storage_backend"] == "local_disk"
    assert attachment["url"]

    list_response = await client.get(
        "/api/v1/attachments", headers=auth_headers, params={"record_id": record_id}
    )
    assert list_response.status_code == 200
    assert [a["id"] for a in list_response.json()] == [attachment["id"]]

    blob_response = await client.get(f"/api/v1/attachments/{attachment['id']}/blob", headers=auth_headers)
    assert blob_response.status_code == 200
    assert blob_response.content == b"fake-jpeg-bytes"


async def test_upload_attachment_without_record_then_link(client, auth_headers):
    record_id = await _create_record(client, auth_headers)

    upload = await client.post(
        "/api/v1/attachments",
        headers=auth_headers,
        files={"file": ("odometer.jpg", b"other-bytes", "image/jpeg")},
    )
    attachment_id = upload.json()["id"]

    empty_list = await client.get("/api/v1/attachments", headers=auth_headers, params={"record_id": record_id})
    assert empty_list.json() == []

    link = await client.post(f"/api/v1/attachments/{attachment_id}/link/{record_id}", headers=auth_headers)
    assert link.status_code == 204

    linked_list = await client.get("/api/v1/attachments", headers=auth_headers, params={"record_id": record_id})
    assert [a["id"] for a in linked_list.json()] == [attachment_id]

    unlink = await client.delete(f"/api/v1/attachments/{attachment_id}/link/{record_id}", headers=auth_headers)
    assert unlink.status_code == 204

    after_unlink = await client.get("/api/v1/attachments", headers=auth_headers, params={"record_id": record_id})
    assert after_unlink.json() == []


async def test_delete_attachment_is_soft_delete(client, auth_headers):
    record_id = await _create_record(client, auth_headers)
    upload = await client.post(
        "/api/v1/attachments",
        headers=auth_headers,
        params={"record_id": record_id},
        files={"file": ("receipt.jpg", b"bytes", "image/jpeg")},
    )
    attachment_id = upload.json()["id"]

    delete = await client.delete(f"/api/v1/attachments/{attachment_id}", headers=auth_headers)
    assert delete.status_code == 204

    get_after_delete = await client.get(f"/api/v1/attachments/{attachment_id}", headers=auth_headers)
    assert get_after_delete.status_code == 404


async def test_upload_attachment_with_client_supplied_id(client, auth_headers):
    record_id = await _create_record(client, auth_headers)
    client_id = str(uuid.uuid4())

    response = await client.post(
        "/api/v1/attachments",
        headers=auth_headers,
        params={"record_id": record_id, "attachment_id": client_id},
        files={"file": ("receipt.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert response.status_code == 201
    assert response.json()["id"] == client_id


async def test_retried_upload_with_same_id_is_idempotent(client, auth_headers):
    record_id = await _create_record(client, auth_headers)
    client_id = str(uuid.uuid4())

    first = await client.post(
        "/api/v1/attachments",
        headers=auth_headers,
        params={"record_id": record_id, "attachment_id": client_id},
        files={"file": ("receipt.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    second = await client.post(
        "/api/v1/attachments",
        headers=auth_headers,
        params={"record_id": record_id, "attachment_id": client_id},
        files={"file": ("receipt.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert second.status_code == 201
    assert second.json() == first.json()

    list_response = await client.get(
        "/api/v1/attachments", headers=auth_headers, params={"record_id": record_id}
    )
    assert [a["id"] for a in list_response.json()] == [client_id]


async def test_client_supplied_id_does_not_leak_across_households(client, auth_headers):
    record_id = await _create_record(client, auth_headers)
    client_id = str(uuid.uuid4())
    await client.post(
        "/api/v1/attachments",
        headers=auth_headers,
        params={"record_id": record_id, "attachment_id": client_id},
        files={"file": ("receipt.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )

    other_user = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "other-id-collision@example.com",
            "password": "a very good password",
            "display_name": "Other",
            "household_name": "Other House",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_user.json()['access_token']}"}

    response = await client.post(
        "/api/v1/attachments",
        headers=other_headers,
        params={"attachment_id": client_id},
        files={"file": ("other-receipt.jpg", b"other-bytes", "image/jpeg")},
    )
    # A colliding id from another household must not return that household's
    # row (no data leak) and must not be silently accepted as if new either
    # (id is a global primary key) -- a clean conflict response is correct,
    # not a fabricated fresh row under someone else's existing id.
    assert response.status_code == 409


async def test_cannot_upload_attachment_for_another_households_record(client, auth_headers):
    record_id = await _create_record(client, auth_headers)

    other_user = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "other@example.com",
            "password": "a very good password",
            "display_name": "Other",
            "household_name": "Other House",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_user.json()['access_token']}"}

    response = await client.post(
        "/api/v1/attachments",
        headers=other_headers,
        params={"record_id": record_id},
        files={"file": ("receipt.jpg", b"bytes", "image/jpeg")},
    )
    assert response.status_code == 404
