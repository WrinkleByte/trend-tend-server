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


async def _create_fuel_log(client, auth_headers) -> str:
    asset = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={"asset_type": "vehicle", "name": "Family Minivan", "vehicle_details": {"current_mileage": 41500}},
    )
    asset_id = asset.json()["id"]
    fuel_log = await client.post(
        "/api/v1/fuel-logs",
        headers=auth_headers,
        json={"asset_id": asset_id, "performed_at": "2026-01-15", "gallons": "10"},
    )
    return fuel_log.json()["id"]


async def _create_trip_log(client, auth_headers) -> str:
    asset = await client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={"asset_type": "vehicle", "name": "Family Minivan", "vehicle_details": {"current_mileage": 41500}},
    )
    asset_id = asset.json()["id"]
    trip_log = await client.post(
        "/api/v1/trip-logs",
        headers=auth_headers,
        json={
            "asset_id": asset_id,
            "performed_at": "2026-01-15T09:00:00Z",
            "purpose": "business",
            "start_odometer": "41500.0",
            "end_odometer": "41542.0",
            "distance": "42.0",
        },
    )
    return trip_log.json()["id"]


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


async def test_upload_attachment_linked_to_fuel_log(client, auth_headers):
    fuel_log_id = await _create_fuel_log(client, auth_headers)

    response = await client.post(
        "/api/v1/attachments",
        headers=auth_headers,
        params={"fuel_log_id": fuel_log_id},
        files={"file": ("pump.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert response.status_code == 201
    attachment = response.json()

    list_response = await client.get(
        "/api/v1/attachments", headers=auth_headers, params={"fuel_log_id": fuel_log_id}
    )
    assert list_response.status_code == 200
    assert [a["id"] for a in list_response.json()] == [attachment["id"]]

    blob_response = await client.get(f"/api/v1/attachments/{attachment['id']}/blob", headers=auth_headers)
    assert blob_response.status_code == 200
    assert blob_response.content == b"fake-jpeg-bytes"


async def test_cannot_upload_attachment_for_another_households_fuel_log(client, auth_headers):
    fuel_log_id = await _create_fuel_log(client, auth_headers)

    other_user = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "other-fuel@example.com",
            "password": "a very good password",
            "display_name": "Other",
            "household_name": "Other House",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_user.json()['access_token']}"}

    response = await client.post(
        "/api/v1/attachments",
        headers=other_headers,
        params={"fuel_log_id": fuel_log_id},
        files={"file": ("pump.jpg", b"bytes", "image/jpeg")},
    )
    assert response.status_code == 404


async def test_upload_attachment_linked_to_trip_log(client, auth_headers):
    trip_log_id = await _create_trip_log(client, auth_headers)

    response = await client.post(
        "/api/v1/attachments",
        headers=auth_headers,
        params={"trip_log_id": trip_log_id},
        files={"file": ("odometer.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert response.status_code == 201
    attachment = response.json()

    list_response = await client.get(
        "/api/v1/attachments", headers=auth_headers, params={"trip_log_id": trip_log_id}
    )
    assert list_response.status_code == 200
    assert [a["id"] for a in list_response.json()] == [attachment["id"]]

    blob_response = await client.get(f"/api/v1/attachments/{attachment['id']}/blob", headers=auth_headers)
    assert blob_response.status_code == 200
    assert blob_response.content == b"fake-jpeg-bytes"


async def test_cannot_upload_attachment_for_another_households_trip_log(client, auth_headers):
    trip_log_id = await _create_trip_log(client, auth_headers)

    other_user = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "other-trip@example.com",
            "password": "a very good password",
            "display_name": "Other",
            "household_name": "Other House",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_user.json()['access_token']}"}

    response = await client.post(
        "/api/v1/attachments",
        headers=other_headers,
        params={"trip_log_id": trip_log_id},
        files={"file": ("odometer.jpg", b"bytes", "image/jpeg")},
    )
    assert response.status_code == 404


async def test_list_attachments_requires_exactly_one_entity_id(client, auth_headers):
    record_id = await _create_record(client, auth_headers)
    fuel_log_id = await _create_fuel_log(client, auth_headers)

    no_params = await client.get("/api/v1/attachments", headers=auth_headers)
    assert no_params.status_code == 400

    both_params = await client.get(
        "/api/v1/attachments",
        headers=auth_headers,
        params={"record_id": record_id, "fuel_log_id": fuel_log_id},
    )
    assert both_params.status_code == 400


# --- Blob serving must not let an upload execute on our origin (review S3) ---
#
# content_type is whatever the uploading client claimed; it is never sniffed
# or validated on the way in. Echoing it back unchecked turned "can upload a
# file" into stored XSS on the API's own origin -- which the web app shares,
# while keeping its tokens in localStorage.


async def test_html_attachment_is_not_served_as_renderable_html(client, auth_headers):
    record_id = await _create_record(client, auth_headers)
    upload = await client.post(
        f"/api/v1/attachments?record_id={record_id}",
        headers=auth_headers,
        files={"file": ("payload.html", b"<script>alert(1)</script>", "text/html")},
    )
    assert upload.status_code == 201

    blob = await client.get(f"/api/v1/attachments/{upload.json()['id']}/blob", headers=auth_headers)
    assert blob.status_code == 200
    # The bytes are still returned intact -- this is about how they're typed.
    assert blob.content == b"<script>alert(1)</script>"
    assert blob.headers["content-type"].startswith("application/octet-stream")
    assert blob.headers["content-disposition"].startswith("attachment")
    assert blob.headers["x-content-type-options"] == "nosniff"


async def test_svg_attachment_is_not_served_inline(client, auth_headers):
    # SVG is an image by extension but an XML document that can carry
    # <script>, so it must be treated as a download, not an image.
    record_id = await _create_record(client, auth_headers)
    upload = await client.post(
        f"/api/v1/attachments?record_id={record_id}",
        headers=auth_headers,
        files={"file": ("x.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml")},
    )
    blob = await client.get(f"/api/v1/attachments/{upload.json()['id']}/blob", headers=auth_headers)
    assert blob.headers["content-type"].startswith("application/octet-stream")
    assert blob.headers["content-disposition"].startswith("attachment")


async def test_real_photo_still_renders_inline(client, auth_headers):
    # The mitigation must not break the actual use case: receipt and
    # odometer photos are shown in-app, not downloaded.
    record_id = await _create_record(client, auth_headers)
    upload = await client.post(
        f"/api/v1/attachments?record_id={record_id}",
        headers=auth_headers,
        files={"file": ("receipt.jpg", b"\xff\xd8\xff\xe0 not really a jpeg", "image/jpeg")},
    )
    blob = await client.get(f"/api/v1/attachments/{upload.json()['id']}/blob", headers=auth_headers)
    assert blob.headers["content-type"].startswith("image/jpeg")
    assert blob.headers["content-disposition"].startswith("inline")


async def test_filename_cannot_inject_content_disposition_directives(client, auth_headers):
    record_id = await _create_record(client, auth_headers)
    upload = await client.post(
        f"/api/v1/attachments?record_id={record_id}",
        headers=auth_headers,
        files={"file": ('ev"il.txt', b"data", "text/plain")},
    )
    blob = await client.get(f"/api/v1/attachments/{upload.json()['id']}/blob", headers=auth_headers)
    disposition = blob.headers["content-disposition"]
    assert disposition.count('"') == 2, disposition


# --- Upload size cap (review S8) ---


async def test_oversized_upload_is_rejected(client, auth_headers):
    from app.api.v1.attachments import MAX_ATTACHMENT_BYTES

    record_id = await _create_record(client, auth_headers)
    too_big = b"x" * (MAX_ATTACHMENT_BYTES + 1024)
    response = await client.post(
        f"/api/v1/attachments?record_id={record_id}",
        headers=auth_headers,
        files={"file": ("huge.bin", too_big, "application/octet-stream")},
    )
    assert response.status_code == 413
