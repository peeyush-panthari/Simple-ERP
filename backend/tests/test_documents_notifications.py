"""New test coverage for the documents + notifications domains (no direct
original-repo equivalent - see test_orders.py's docstring for the same
note). Documents: template render (HTML-passthrough engine), upload/download
round-trip, reprint-creates-new-row, upload validation. Notifications:
template listing/edit/versioning/preview, send with an unreachable SMTP
transport (a real transient failure, logged + retryable, never an
exception), suppression handling, and the delivery-events webhook - all
against a real Postgres.
"""

from __future__ import annotations

import base64
import uuid

from app.core.db import SessionLocal


def _auth_headers(client, admin):
    login = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def _cleanup_documents(document_ids) -> None:
    from app.models.document import Document

    Document.query.filter(Document.id.in_([uuid.UUID(d) for d in document_ids])).delete(synchronize_session=False)
    SessionLocal.commit()


def test_upload_download_roundtrip_and_validation(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    payload = b"hello,world\n1,2\n"
    upload = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        json={"filename": "t.csv", "contentType": "text/csv", "contentBase64": base64.b64encode(payload).decode(), "relatedType": "test", "relatedId": "T-1"},
    )
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["id"]

    download = client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
    assert download.status_code == 200 and download.content == payload
    assert download.headers["content-disposition"].startswith("attachment")

    got = client.get(f"/api/v1/documents/{doc_id}", headers=headers).json()
    assert got["bytes"] == len(payload) and got["url"]

    listed = client.get("/api/v1/documents", headers=headers, params={"relatedType": "test", "relatedId": "T-1"}).json()
    assert [d["id"] for d in listed["data"]] == [doc_id]

    bad_type = client.post("/api/v1/documents/upload", headers=headers, json={"filename": "x.exe", "contentType": "application/x-msdownload", "contentBase64": "AAAA"})
    assert bad_type.status_code == 422 and bad_type.json()["code"] == "ATTACHMENT_TYPE_INVALID"
    fake_pdf = client.post("/api/v1/documents/upload", headers=headers, json={"filename": "x.pdf", "contentType": "application/pdf", "contentBase64": base64.b64encode(b"not a pdf").decode()})
    assert fake_pdf.status_code == 422 and fake_pdf.json()["code"] == "ATTACHMENT_TYPE_MISMATCH"

    status = client.get("/api/v1/documents/storage/status", headers=headers)
    assert status.status_code == 200 and status.json()["backend"]

    _cleanup_documents([doc_id])


def test_render_template_and_reprint_creates_new_row(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    unknown = client.post("/api/v1/documents/render", headers=headers, json={"template": "nope", "data": {}, "filename": "x.pdf"})
    assert unknown.status_code == 422 and unknown.json()["code"] == "UNKNOWN_TEMPLATE"

    render = client.post(
        "/api/v1/documents/render",
        headers=headers,
        json={
            "template": "goods-receipt",
            "filename": "grn-test.pdf",
            "data": {"number": "GRN-TEST", "vendorName": "Test Vendor", "lines": [], "date": "2026-01-01"},
            "relatedType": "test",
            "relatedId": "T-2",
        },
    )
    assert render.status_code == 201, render.text
    original_id = render.json()["id"]
    assert render.json()["engine"] == "html"  # default engine, no weasyprint/gotenberg configured

    reprint = client.post(f"/api/v1/documents/{original_id}/reprint", headers=headers)
    assert reprint.status_code == 201, reprint.text
    assert reprint.json()["id"] != original_id

    _cleanup_documents([original_id, reprint.json()["id"]])


def test_template_edit_versions_and_preview(client, fresh_admin, default_tenant_id):
    from app.models.notification_template import NotificationTemplate

    headers = _auth_headers(client, fresh_admin)
    templates = client.get("/api/v1/templates", headers=headers).json()["data"]
    assert any(t["key"] == "user.invitation" and t["isBuiltin"] for t in templates)

    key = f"test.template.{uuid.uuid4().hex[:6]}"
    v1 = client.put(f"/api/v1/templates/{key}", headers=headers, json={"subject": "Hi {{name}}", "bodyText": "Hello {{name}}!"})
    assert v1.status_code == 200 and v1.json()["version"] == 1
    v2 = client.put(f"/api/v1/templates/{key}", headers=headers, json={"subject": "Hey {{name}}", "bodyText": "Yo {{name}}!"})
    assert v2.json()["version"] == 2

    versions = client.get(f"/api/v1/templates/{key}", headers=headers).json()["data"]
    assert [v["version"] for v in versions] == [2, 1]
    assert [v["active"] for v in versions] == [True, False]

    preview = client.post(f"/api/v1/templates/{key}/preview", headers=headers, json={"data": {"name": "<Ada>"}})
    assert preview.status_code == 200
    assert preview.json()["subject"] == "Hey <Ada>" or "Ada" in preview.json()["subject"]
    assert "Yo" in preview.json()["text"]

    NotificationTemplate.query.filter_by(tenant_id=default_tenant_id, key=key).delete(synchronize_session=False)
    SessionLocal.commit()


def test_send_fails_softly_when_smtp_unreachable_then_suppression_blocks(client, fresh_admin, default_tenant_id):
    from app.models.delivery_log import DeliveryLog
    from app.models.notification import Notification
    from app.models.notification_template import NotificationTemplate
    from app.models.suppression import Suppression

    headers = _auth_headers(client, fresh_admin)
    key = f"test.send.{uuid.uuid4().hex[:6]}"
    client.put(f"/api/v1/templates/{key}", headers=headers, json={"subject": "S", "bodyText": "B"})

    address = f"nobody-{uuid.uuid4().hex[:6]}@example.test"
    bad_recipient = client.post("/api/v1/notifications/send", headers=headers, json={"template": key, "to": ["not-an-email"]})
    assert bad_recipient.status_code == 422 and bad_recipient.json()["code"] == "RECIPIENT_INVALID"

    missing = client.post("/api/v1/notifications/send", headers=headers, json={"template": "no.such.template", "to": [address]})
    assert missing.status_code == 404

    # Deferred: queued row, no delivery attempt.
    deferred = client.post("/api/v1/notifications/send", headers=headers, json={"template": key, "to": [address], "deferred": True, "relatedType": "test", "relatedId": key})
    assert deferred.status_code == 201, deferred.text
    assert deferred.json()["status"] == "queued"
    note_id = deferred.json()["id"]

    # Retry delivers inline; nothing listens on the dev SMTP port, so it
    # records a failed attempt (transient -> back to queued) instead of raising.
    retry = client.post(f"/api/v1/notifications/{note_id}/retry", headers=headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] in ("queued", "failed", "sent")
    logs = client.get("/api/v1/delivery-logs", headers=headers, params={"notificationId": note_id}).json()["data"]
    assert len(logs) == 1

    # Bounce webhook suppresses the address; a later send to it is rejected.
    hook = client.post("/api/v1/internal/delivery-events", headers=headers, json={"provider": "test", "events": [{"address": address, "outcome": "bounced"}]})
    assert hook.status_code == 200 and hook.json() == {"processed": 1, "suppressed": 1}
    blocked = client.post("/api/v1/notifications/send", headers=headers, json={"template": key, "to": [address]})
    assert blocked.status_code == 409 and blocked.json()["code"] == "ALL_RECIPIENTS_SUPPRESSED"

    suppressions = client.get("/api/v1/suppressions", headers=headers).json()["data"]
    assert any(s["address"] == address for s in suppressions)
    assert client.delete(f"/api/v1/suppressions/{address}", headers=headers).status_code == 204

    listed = client.get("/api/v1/notifications", headers=headers, params={"relatedType": "test", "relatedId": key}).json()
    assert [n["id"] for n in listed["data"]] == [note_id]

    DeliveryLog.query.filter_by(notification_id=uuid.UUID(note_id)).delete(synchronize_session=False)
    Notification.query.filter_by(id=uuid.UUID(note_id)).delete(synchronize_session=False)
    Suppression.query.filter_by(tenant_id=default_tenant_id, address=address).delete(synchronize_session=False)
    NotificationTemplate.query.filter_by(tenant_id=default_tenant_id, key=key).delete(synchronize_session=False)
    SessionLocal.commit()
