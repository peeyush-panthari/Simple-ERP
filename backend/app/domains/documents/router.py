"""GET/POST /documents, GET /documents/{id}, GET /documents/{id}/download,
POST /documents/{id}/reprint, POST /documents/upload, POST /documents/render,
GET /documents/storage/status. Ported 1:1 (behavior) from
backend_py/app/routes/documents.py.

Real, human-callable routes with real permission checks - already-built
modules (orders, procurement) call document_repo directly, bypassing this
gate entirely, matching what the original's internal-token bypass achieved.
"""

from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth import Actor, require_permission
from app.core.config import settings
from app.core.db import session
from app.core.errors import conflict
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.pagination import ListQuery, list_response, offset_of
from app.models.document import Document
from app.services import document_pdf, document_repo, document_storage

router = APIRouter(prefix="/api/v1", tags=["documents"])


class RenderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template: str
    data: dict = Field(default_factory=dict)
    filename: str = Field(min_length=1, max_length=200)
    relatedType: str | None = Field(default=None, max_length=40)
    relatedId: str | None = Field(default=None, max_length=80)


class UploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=200)
    contentType: str = Field(min_length=3, max_length=120)
    contentBase64: str = Field(min_length=1)
    relatedType: str | None = Field(default=None, max_length=40)
    relatedId: str | None = Field(default=None, max_length=80)


@router.get("/documents")
def list_documents(
    actor: Actor = Depends(require_permission("document:read")),
    query: ListQuery = Depends(),
    relatedType: str | None = None,
    relatedId: str | None = None,
    template: str | None = None,
):
    q = Document.query.filter(Document.tenant_id == actor["tenant_id"])
    if relatedType:
        q = q.filter(Document.related_type == relatedType)
    if relatedId:
        q = q.filter(Document.related_id == relatedId)
    if template:
        q = q.filter(Document.template == template)
    if query.q:
        q = q.filter(Document.filename.ilike(f"%{query.q}%"))

    total = q.count()
    rows = q.order_by(Document.created_at.desc()).limit(query.limit).offset(offset_of(query)).all()
    return list_response([document_repo.to_api(r) for r in rows], query, total)


# Registered before /documents/{id} so "storage" isn't captured as an id.
@router.get("/documents/storage/status")
def storage_status(actor: Actor = Depends(require_permission("document:read"))):
    backend = document_storage.active_backend()
    return {
        "backend": backend,
        "bucket": settings.s3_bucket if backend == "s3" else None,
        "pdfEngine": settings.pdf_engine,
        "note": f"PDF engine '{settings.pdf_engine}' is {'available' if document_pdf.pdf_engine_available() else 'unavailable - falling back to the next tier'}.",
    }


@router.get("/documents/{id}")
def get_document(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("document:read"))):
    row = document_repo.require_document(actor["tenant_id"], id)
    resp = document_repo.to_api(row)
    resp["url"] = document_storage.url_for(row.id, row.storage_key)
    return resp


@router.get("/documents/{id}/download")
def download_document(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("document:read"))):
    row = document_repo.require_document(actor["tenant_id"], id)
    if row.scan_status == "infected":
        raise conflict(f"{row.filename} failed a malware scan and cannot be downloaded", code="DOCUMENT_INFECTED")
    document_repo.ensure_rendered(row)  # ASYNC_PDF: the worker may not have got to it yet
    try:
        data = document_storage.get(row.storage_key)
    except FileNotFoundError:
        # Local dev storage lives under /tmp, which doesn't survive a
        # machine reboot - the Document row can outlive its file.
        raise conflict(f"{row.filename} is no longer available in storage", code="DOCUMENT_FILE_MISSING")
    disposition = "inline" if row.content_type == "application/pdf" else "attachment"
    return Response(content=data, media_type=row.content_type, headers={"Content-Disposition": f'{disposition}; filename="{row.filename}"'})


@router.post("/documents/render", status_code=201)
def render_document_route(body: RenderBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("document:write"))):
    tenant_id = actor["tenant_id"]

    def _do():
        result = document_repo.render_document(
            tenant_id, template=body.template, data=body.data, filename=body.filename,
            related_type=body.relatedType, related_id=body.relatedId, created_by=str(actor["user_id"]),
        )
        session.commit()
        return 201, result

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


@router.post("/documents/upload", status_code=201)
def upload_document_route(body: UploadBody, actor: Actor = Depends(require_permission("document:write"))):
    result = document_repo.upload_document(
        actor["tenant_id"], filename=body.filename, content_type=body.contentType, content_base64=body.contentBase64,
        related_type=body.relatedType, related_id=body.relatedId, created_by=str(actor["user_id"]),
    )
    session.commit()
    return result


@router.post("/documents/{id}/reprint", status_code=201)
def reprint_document_route(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("document:write"))):
    result = document_repo.reprint_document(actor["tenant_id"], id, created_by=str(actor["user_id"]))
    session.commit()
    return result
