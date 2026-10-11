"""Document rendering/upload/retrieval. Ported 1:1 from
backend_py/app/services/document_repo.py (render_document/reprint_document
restored now that document_pdf/document_templates are ported).

One addition: with ASYNC_PDF on, `render_document` records the document and
returns without rendering; `complete_render` (run by the worker, or lazily by a
download that beats it) fills the same row in afterwards. See config.async_pdf.
"""

from __future__ import annotations

import base64
import uuid

from app.core.config import settings
from app.core.db import session
from app.core import messaging
from app.core.errors import not_found, rule_violation
from app.models.document import Document
from app.services import document_pdf, document_storage
from app.services.document_templates import TEMPLATES

ALLOWED_UPLOAD_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "text/csv",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def find_document(tenant_id: uuid.UUID, id: uuid.UUID) -> Document | None:
    return Document.query.filter_by(tenant_id=tenant_id, id=id).first()


def require_document(tenant_id: uuid.UUID, id: uuid.UUID) -> Document:
    row = find_document(tenant_id, id)
    if not row:
        raise not_found(f"Document {id}")
    return row


def to_api(row: Document) -> dict:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "template": row.template,
        "filename": row.filename,
        "contentType": row.content_type,
        "bytes": row.bytes_,
        "checksum": row.checksum,
        "storageBackend": row.storage_backend,
        "relatedType": row.related_type,
        "relatedId": row.related_id,
        "scanStatus": row.scan_status,
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def upload_document(
    tenant_id: uuid.UUID,
    *,
    filename: str,
    content_type: str,
    content_base64: str,
    related_type: str | None = None,
    related_id: str | None = None,
    created_by: str | None = None,
) -> dict:
    """No idempotency handling (unlike render_document) - a retry duplicates
    the row, matching the original exactly."""
    if content_type not in ALLOWED_UPLOAD_MIME:
        raise rule_violation(f"Attachment type {content_type} is not allowed", code="ATTACHMENT_TYPE_INVALID")
    try:
        raw = base64.b64decode(content_base64, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise rule_violation("Attachment content is not valid base64", code="ATTACHMENT_INVALID") from exc
    if not raw:
        raise rule_violation("Attachment is empty", code="ATTACHMENT_EMPTY")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise rule_violation(f"Attachment exceeds the {MAX_UPLOAD_BYTES} byte limit", code="ATTACHMENT_TOO_LARGE")
    if content_type == "application/pdf" and raw[:4] != b"%PDF":
        raise rule_violation("File content does not match its declared PDF type", code="ATTACHMENT_TYPE_MISMATCH")

    key = document_storage.build_key(tenant_id, filename)
    document_storage.put(key, raw, content_type)

    # MALWARE_SCANNER_URL is dead config, matching the original - a 'pending'
    # document never actually gets scanned or advanced.
    scan_status = "pending" if settings.malware_scanner_url else "not_required"
    row = Document(
        tenant_id=tenant_id,
        kind="uploaded",
        filename=filename,
        content_type=content_type,
        bytes_=len(raw),
        checksum=document_storage.checksum_of(raw),
        storage_backend=document_storage.active_backend(),
        storage_key=key,
        related_type=related_type,
        related_id=related_id,
        scan_status=scan_status,
        created_by=created_by,
    )
    session.add(row)
    session.flush()

    return {"id": str(row.id), "url": document_storage.url_for(row.id, key), "filename": filename, "bytes": row.bytes_, "scanStatus": scan_status}


def render_document(
    tenant_id: uuid.UUID,
    *,
    template: str,
    data: dict,
    filename: str,
    related_type: str | None = None,
    related_id: str | None = None,
    created_by: str | None = None,
) -> dict:
    """Direct-call equivalent of POST /documents/render. Always succeeds -
    the PDF engine's terminal tier is a raw HTML passthrough. Persists
    render_data so /documents/:id/reprint can regenerate later."""
    builder = TEMPLATES.get(template)
    if not builder:
        raise rule_violation(f"Unknown document template: {template}", code="UNKNOWN_TEMPLATE")

    html = builder(data)  # cheap, and surfaces bad template data in the request either way
    if _defer_pdf():
        return _record_pending(tenant_id, template=template, data=data, filename=filename, related_type=related_type, related_id=related_id, created_by=created_by)
    result = document_pdf.html_to_pdf(html)
    actual_filename = filename if result["engine"] != "html" else _with_html_extension(filename)

    key = document_storage.build_key(tenant_id, actual_filename)
    document_storage.put(key, result["body"], result["content_type"])

    row = Document(
        tenant_id=tenant_id,
        kind="generated",
        template=template,
        filename=actual_filename,
        content_type=result["content_type"],
        bytes_=len(result["body"]),
        checksum=document_storage.checksum_of(result["body"]),
        storage_backend=document_storage.active_backend(),
        storage_key=key,
        related_type=related_type,
        related_id=related_id,
        render_data=data,
        scan_status="not_required",
        created_by=created_by,
    )
    session.add(row)
    session.flush()

    return {"id": str(row.id), "url": document_storage.url_for(row.id, key), "filename": actual_filename, "bytes": row.bytes_, "contentType": row.content_type, "engine": result["engine"]}


def _defer_pdf() -> bool:
    """Only worth deferring when a real (slow) engine is configured - the html engine is instant."""
    return settings.async_pdf and settings.pdf_engine != "html"


def is_pending(row: Document) -> bool:
    """A generated document whose PDF has not been rendered yet: recorded, but nothing stored."""
    return row.kind == "generated" and row.checksum is None and row.bytes_ == 0


def _record_pending(tenant_id: uuid.UUID, *, template: str, data: dict, filename: str, related_type, related_id, created_by) -> dict:
    """Same row (same id, url and - unless the engine later falls back to HTML - filename) that a synchronous
    render would have produced, minus the stored body. A message naming it is published after commit."""
    key = document_storage.build_key(tenant_id, filename)
    row = Document(
        tenant_id=tenant_id,
        kind="generated",
        template=template,
        filename=filename,
        content_type="application/pdf",
        bytes_=0,
        checksum=None,
        storage_backend=document_storage.active_backend(),
        storage_key=key,
        related_type=related_type,
        related_id=related_id,
        render_data=data,
        scan_status="not_required",
        created_by=created_by,
    )
    session.add(row)
    session.flush()
    messaging.publish_after_commit(settings.document_queue, {"tenantId": str(tenant_id), "documentId": str(row.id)})
    return {"id": str(row.id), "url": document_storage.url_for(row.id, key), "filename": filename, "bytes": 0, "contentType": "application/pdf", "engine": "pending"}


def complete_render(tenant_id: uuid.UUID, id: uuid.UUID) -> str | None:
    """Renders a pending document's PDF and stores it. Idempotent: locks the row, and does nothing when the
    document is already rendered (a duplicate message, or the worker and a download racing). Does not
    commit. Returns the engine used, or None if there was nothing to do."""
    row = Document.query.filter_by(tenant_id=tenant_id, id=id).with_for_update().first()
    if row is None or not is_pending(row):
        return None
    builder = TEMPLATES.get(row.template or "")
    if builder is None or row.render_data is None:
        raise rule_violation(f"{row.filename} cannot be rendered: no template data", code="DOCUMENT_NOT_REPRINTABLE")
    result = document_pdf.html_to_pdf(builder(row.render_data))
    if result["engine"] == "html":  # every engine failed and the terminal tier is a raw HTML passthrough
        row.filename = _with_html_extension(row.filename)
    document_storage.put(row.storage_key, result["body"], result["content_type"])
    row.content_type = result["content_type"]
    row.bytes_ = len(result["body"])
    row.checksum = document_storage.checksum_of(result["body"])
    session.flush()
    return result["engine"]


def ensure_rendered(row: Document) -> None:
    """Call before reading a document's bytes: renders it now if the worker has not yet. The lazy half of
    ASYNC_PDF - what keeps a download correct with no worker running."""
    if is_pending(row):
        complete_render(row.tenant_id, row.id)
        session.commit()
        session.refresh(row)


def _with_html_extension(filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        return filename[: -len(".pdf")] + ".html"
    return filename


def reprint_document(tenant_id: uuid.UUID, id: uuid.UUID, *, created_by: str | None = None) -> dict:
    """Re-renders from the stored render_data snapshot; creates a NEW row,
    never overwrites the original."""
    original = require_document(tenant_id, id)
    if original.kind != "generated" or not original.template or original.render_data is None:
        raise rule_violation(f"{original.filename} was not generated from a template and cannot be reprinted", code="DOCUMENT_NOT_REPRINTABLE")
    return render_document(tenant_id, template=original.template, data=original.render_data, filename=original.filename, related_type=original.related_type, related_id=original.related_id, created_by=created_by)
