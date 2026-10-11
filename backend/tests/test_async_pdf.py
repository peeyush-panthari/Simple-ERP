"""ASYNC_PDF: generated documents are recorded in the request and rendered by the worker afterwards.

What matters and is checked here: the API contract is unchanged (same row id, url and filename), nothing is
published for a rolled-back request, rendering is idempotent, a download that beats the worker renders on the
spot (so correctness never depends on the worker), and the worker's sweep finds a document whose message
was lost. With the flag off (the default) nothing changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core import messaging
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.document import Document
from app.services import document_pdf, document_repo, document_storage
from tests.test_infra import FakeBroker

GRN_DATA = {"number": "GRN-ASYNC", "vendorName": "Async Vendor", "lines": [], "date": "2026-01-01"}


def _headers(client, admin):
    login = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


@pytest.fixture
def broker():
    fake = FakeBroker()
    messaging.set_broker(fake)
    yield fake
    messaging.set_broker(None)


@pytest.fixture
def async_pdf(monkeypatch, broker):
    """ASYNC_PDF on with a stand-in for a real engine (the html engine is never deferred)."""
    monkeypatch.setattr(settings, "async_pdf", True)
    monkeypatch.setattr(settings, "pdf_engine", "weasyprint")
    calls = []

    def fake_pdf(html):
        calls.append(html)
        return {"body": b"%PDF-1.7 async-test", "content_type": "application/pdf", "engine": "weasyprint"}

    monkeypatch.setattr(document_pdf, "html_to_pdf", fake_pdf)
    return calls


@pytest.fixture
def created():
    ids = []
    yield ids
    if ids:
        Document.query.filter(Document.id.in_(ids)).delete(synchronize_session=False)
        SessionLocal.commit()


def _render(tenant_id, filename="async-test.pdf"):
    return document_repo.render_document(tenant_id, template="goods-receipt", data=GRN_DATA, filename=filename, related_type="test", related_id="ASYNC")


def test_off_by_default_renders_inline(default_tenant_id, broker, created):
    result = _render(default_tenant_id)
    SessionLocal.commit()
    created.append(uuid.UUID(result["id"]))
    assert result["engine"] == "html" and result["bytes"] > 0
    assert broker.published == []


def test_async_records_the_document_and_publishes_after_commit(default_tenant_id, async_pdf, broker, created):
    result = _render(default_tenant_id)
    created.append(uuid.UUID(result["id"]))
    assert result["engine"] == "pending" and result["bytes"] == 0 and result["filename"] == "async-test.pdf"
    assert broker.published == []  # nothing goes out until the transaction commits
    SessionLocal.commit()
    assert broker.published == [(settings.document_queue, {"tenantId": str(default_tenant_id), "documentId": result["id"]})]
    assert async_pdf == []  # and no PDF was rendered in the request

    row = Document.query.filter_by(id=uuid.UUID(result["id"])).one()
    assert document_repo.is_pending(row)
    with pytest.raises(FileNotFoundError):
        document_storage.get(row.storage_key)


def test_a_rolled_back_request_publishes_nothing(default_tenant_id, async_pdf, broker):
    _render(default_tenant_id)
    SessionLocal.rollback()
    SessionLocal.commit()
    assert broker.published == []


def test_complete_render_fills_the_same_row_and_is_idempotent(default_tenant_id, async_pdf, created):
    result = _render(default_tenant_id)
    SessionLocal.commit()
    doc_id = uuid.UUID(result["id"])
    created.append(doc_id)

    assert document_repo.complete_render(default_tenant_id, doc_id) == "weasyprint"
    SessionLocal.commit()
    row = Document.query.filter_by(id=doc_id).one()
    assert not document_repo.is_pending(row)
    assert row.filename == "async-test.pdf" and row.content_type == "application/pdf" and row.bytes_ == len(b"%PDF-1.7 async-test")
    assert document_storage.get(row.storage_key) == b"%PDF-1.7 async-test"

    assert document_repo.complete_render(default_tenant_id, doc_id) is None  # a duplicate message is a no-op
    assert len(async_pdf) == 1


def test_engine_fallback_to_html_renames_the_file(default_tenant_id, monkeypatch, async_pdf, created):
    monkeypatch.setattr(document_pdf, "html_to_pdf", lambda html: {"body": b"<html>x</html>", "content_type": "text/html; charset=utf-8", "engine": "html"})
    result = _render(default_tenant_id)
    SessionLocal.commit()
    doc_id = uuid.UUID(result["id"])
    created.append(doc_id)
    assert document_repo.complete_render(default_tenant_id, doc_id) == "html"
    SessionLocal.commit()
    assert Document.query.filter_by(id=doc_id).one().filename == "async-test.html"


def test_a_download_that_beats_the_worker_renders_on_the_spot(client, fresh_admin, async_pdf, created):
    headers = _headers(client, fresh_admin)
    render = client.post("/api/v1/documents/render", headers=headers, json={"template": "goods-receipt", "filename": "lazy.pdf", "data": GRN_DATA})
    assert render.status_code == 201, render.text
    assert render.json()["engine"] == "pending"
    doc_id = render.json()["id"]
    created.append(uuid.UUID(doc_id))

    download = client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
    assert download.status_code == 200, download.text
    assert download.data == b"%PDF-1.7 async-test"
    assert download.content_type.startswith("application/pdf")
    assert client.get(f"/api/v1/documents/{doc_id}/download", headers=headers).data == download.data
    assert len(async_pdf) == 1  # rendered once, then served from storage


def test_worker_handles_a_message_and_sweeps_up_lost_ones(default_tenant_id, async_pdf, created):
    from app.worker import main as worker

    via_message = _render(default_tenant_id, "via-message.pdf")
    lost = _render(default_tenant_id, "lost.pdf")
    fresh = _render(default_tenant_id, "fresh.pdf")
    SessionLocal.commit()
    ids = {name: uuid.UUID(r["id"]) for name, r in {"message": via_message, "lost": lost, "fresh": fresh}.items()}
    created.extend(ids.values())
    old = datetime.now(timezone.utc) - timedelta(minutes=5)
    Document.query.filter(Document.id.in_([ids["lost"]])).update({"created_at": old}, synchronize_session=False)
    SessionLocal.commit()

    worker.handle_document_message(f'{{"tenantId": "{default_tenant_id}", "documentId": "{ids["message"]}"}}'.encode())
    assert worker.sweep_documents_once() >= 1

    pending = {name: document_repo.is_pending(Document.query.filter_by(id=i).one()) for name, i in ids.items()}
    assert pending == {"message": False, "lost": False, "fresh": True}  # the fresh one is left to its own message
    SessionLocal.remove()
