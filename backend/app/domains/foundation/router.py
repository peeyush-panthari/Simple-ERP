"""Foundation / master data: factories, tenant + auth policy + system roles,
party types, sticker sizes.
"""

from __future__ import annotations

import csv
import io
import re
import uuid as uuid_mod
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Response
from pydantic import ValidationError
from sqlalchemy import func, or_

from app.core.access_scope import assert_factory_in_scope, scope_query_by_factory
from app.core.audit import audit
from app.core.config import settings
from app.core.auth import Actor, CurrentActor, require_any_permission, require_permission
from app.core.db import session
from app.core.errors import ProblemError, conflict, not_found, rule_violation
from app.core.pagination import ListQuery, list_response, offset_of
from app.core.permissions import SYSTEM_ROLES
from app.domains.foundation.schemas import (
    AuthPolicyPatchBody,
    BulkUploadBody,
    CreatePartyTypeBody,
    FactoryBody,
    PatchFactoryBody,
    PatchPartyTypeBody,
    PatchStickerSizeBody,
    StickerSizeBody,
)
from app.models.auth_policy import AuthPolicy
from app.models.factory import Factory
from app.models.party_type import PartyType
from app.models.sticker_size import StickerSize
from app.models.tenant import Tenant
from app.models.warehouse import Warehouse
from app.services.sequences import next_factory_code

router = APIRouter(prefix="/api/v1", tags=["foundation"])


# ============================================================================
# factories
# ============================================================================


def to_factory_api(row: Factory) -> dict:
    return {
        "id": str(row.id),
        "code": row.code,
        "name": row.name,
        "status": row.status,
        "addressLine1": row.address_line1,
        "addressLine2": row.address_line2,
        "city": row.city,
        "stateCode": row.state_code,
        "postalCode": row.postal_code,
        "country": row.country,
        "contactEmail": row.contact_email,
        "contactPhone": row.contact_phone,
        "notes": row.notes,
    }


#  Users & Roles calls this to populate a role assignment's factory-scope
#  picker - not only the Factory & Warehouse module itself - so it also
#  accepts user:read. Full CRUD stays behind warehouse:write.
_FACTORY_LOOKUP_PERMISSIONS = ("warehouse:read", "user:read")


@router.get("/factories")
def list_factories(actor: Actor = Depends(require_any_permission(*_FACTORY_LOOKUP_PERMISSIONS)), query: ListQuery = Depends(), status: str | None = None):
    tenant_id = actor["tenant_id"]

    q = Factory.query.filter(Factory.tenant_id == tenant_id)
    q = scope_query_by_factory(q, Factory.id, actor)
    if status:
        q = q.filter(Factory.status == status)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(Factory.code.ilike(like), Factory.name.ilike(like)))

    total = q.count()
    rows = q.order_by(Factory.code).limit(query.limit).offset(offset_of(query)).all()

    # One grouped count for the page, not one count query per factory.
    warehouse_counts = (
        dict(session.query(Warehouse.factory_id, func.count()).filter(Warehouse.factory_id.in_([r.id for r in rows])).group_by(Warehouse.factory_id).all())
        if rows
        else {}
    )

    data = []
    for r in rows:
        api = to_factory_api(r)
        api["warehouseCount"] = warehouse_counts.get(r.id, 0)
        data.append(api)

    return list_response(data, query, total)


def _create_factory(tenant_id, actor: Actor, body: FactoryBody) -> Factory:
    """Shared by the single create route and the bulk-upload route, so a
    factory created either way goes through the exact same code numbering
    and audit trail."""
    code = body.code or next_factory_code(tenant_id)
    if Factory.query.filter(Factory.tenant_id == tenant_id, func.upper(Factory.code) == code.upper()).first():
        raise conflict(f"Factory code {code} is already in use", code="FACTORY_CODE_TAKEN")

    row = Factory(
        tenant_id=tenant_id,
        code=code,
        name=body.name,
        address_line1=body.addressLine1,
        address_line2=body.addressLine2,
        city=body.city,
        state_code=body.stateCode,
        postal_code=body.postalCode,
        country=body.country,
        contact_email=body.contactEmail,
        contact_phone=body.contactPhone,
        notes=body.notes,
        status=body.status,
    )
    session.add(row)
    session.flush()

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="factory.created", entity_type="factory", entity_id=str(row.id))
    session.commit()
    return row


@router.post("/factories", status_code=201)
def create_factory(body: FactoryBody, actor: Actor = Depends(require_permission("warehouse:write"))):
    row = _create_factory(actor["tenant_id"], actor, body)
    return to_factory_api(row)


FACTORY_BULK_UPLOAD_REQUIRED_COLUMNS = ["name"]


@router.post("/factories/bulk-upload")
def bulk_upload_factories(body: BulkUploadBody, actor: Actor = Depends(require_permission("warehouse:write"))):
    """Creates many factories from one CSV in a single request - one row per
    factory. A bad row is reported as an error and skipped, it never fails
    rows that already validated fine."""
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in FACTORY_BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    results = []
    for row_number, raw_row in enumerate(reader, start=2):  # header is row 1
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k}
        if not any(row.values()):
            continue
        label = row.get("name") or f"(row {row_number})"

        try:
            create_body = FactoryBody(
                code=row.get("code") or None,
                name=row.get("name") or "",
                addressLine1=row.get("addressLine1") or None,
                addressLine2=row.get("addressLine2") or None,
                city=row.get("city") or None,
                stateCode=row.get("stateCode") or None,
                postalCode=row.get("postalCode") or None,
                country=row.get("country") or "IN",
                contactEmail=row.get("contactEmail") or None,
                contactPhone=row.get("contactPhone") or None,
                notes=row.get("notes") or None,
                status=row.get("status") or "active",
            )
        except ValidationError as exc:
            results.append({"row": row_number, "name": label, "status": "error", "error": exc.errors()[0].get("msg", "invalid data"), "rowData": row})
            continue

        try:
            factory = _create_factory(tenant_id, actor, create_body)
            results.append({"row": row_number, "name": label, "status": "success", "code": factory.code, "rowData": row})
        except ProblemError as exc:
            session.rollback()
            results.append({"row": row_number, "name": label, "status": "error", "error": exc.detail, "rowData": row})
        except Exception as exc:  # noqa: BLE001 - one bad row must not fail the whole batch
            session.rollback()
            results.append({"row": row_number, "name": label, "status": "error", "error": str(exc), "rowData": row})

    success_count = sum(1 for r in results if r["status"] == "success")
    return {
        "summary": {"totalRows": len(results), "successCount": success_count, "errorCount": len(results) - success_count},
        "results": [
            {"row": r["row"], "name": r["name"], "status": r["status"], "code": r.get("code"), "error": r.get("error"), "rowData": r["rowData"] if r["status"] == "error" else {}}
            for r in results
        ],
    }


@router.patch("/factories/{id}")
def patch_factory(id: uuid_mod.UUID, body: PatchFactoryBody, actor: Actor = Depends(require_permission("warehouse:write"))):
    tenant_id = actor["tenant_id"]

    row = Factory.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not row:
        raise not_found("Factory")
    assert_factory_in_scope(actor, row.id)

    if body.code is not None:
        if Factory.query.filter(Factory.tenant_id == tenant_id, Factory.id != id, func.upper(Factory.code) == body.code.upper()).first():
            raise conflict(f"Factory code {body.code} is already in use", code="FACTORY_CODE_TAKEN")
        row.code = body.code
    if body.name is not None:
        row.name = body.name
    if "addressLine1" in body.model_fields_set:
        row.address_line1 = body.addressLine1
    if "addressLine2" in body.model_fields_set:
        row.address_line2 = body.addressLine2
    if "city" in body.model_fields_set:
        row.city = body.city
    if "stateCode" in body.model_fields_set:
        row.state_code = body.stateCode
    if "postalCode" in body.model_fields_set:
        row.postal_code = body.postalCode
    if body.country is not None:
        row.country = body.country
    if "contactEmail" in body.model_fields_set:
        row.contact_email = body.contactEmail
    if "contactPhone" in body.model_fields_set:
        row.contact_phone = body.contactPhone
    if "notes" in body.model_fields_set:
        row.notes = body.notes
    if body.status is not None:
        row.status = body.status

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="factory.updated", entity_type="factory", entity_id=str(id))
    session.commit()

    return to_factory_api(row)


# ============================================================================
# tenants / auth policy / system roles
# ============================================================================


def _policy_to_api(policy: AuthPolicy) -> dict:
    return {
        "tenantId": str(policy.tenant_id),
        "passwordMinLength": policy.password_min_length,
        "passwordRequireSymbol": policy.password_require_symbol,
        "passwordRequireNumber": policy.password_require_number,
        "passwordRequireMixedCase": policy.password_require_mixed_case,
        "passwordMaxAgeDays": policy.password_max_age_days,
        "passwordHistory": policy.password_history,
        "mfaRequired": policy.mfa_required,
        "maxFailedAttempts": policy.max_failed_attempts,
        "lockoutMinutes": policy.lockout_minutes,
        "sessionIdleMinutes": policy.session_idle_minutes,
        "inactiveUserDays": policy.inactive_user_days,
    }


@router.get("/tenants/current")
def current_tenant(actor: CurrentActor):
    tenant = session.get(Tenant, actor["tenant_id"])
    if not tenant:
        raise not_found("Tenant")
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "country": tenant.country,
        "baseCurrency": tenant.base_currency,
        "settings": tenant.settings,
    }


@router.get("/auth-policy")
def get_auth_policy(actor: Actor = Depends(require_permission("role:read"))):
    policy = session.get(AuthPolicy, actor["tenant_id"])
    return _policy_to_api(policy) if policy else {}


@router.patch("/auth-policy")
def patch_auth_policy(body: AuthPolicyPatchBody, actor: Actor = Depends(require_permission("system:admin"))):
    policy = session.get(AuthPolicy, actor["tenant_id"])
    if policy is None:
        policy = AuthPolicy(tenant_id=actor["tenant_id"])
        session.add(policy)
        session.flush()

    if body.passwordMinLength is not None:
        policy.password_min_length = body.passwordMinLength
    if body.passwordMaxAgeDays is not None:
        policy.password_max_age_days = body.passwordMaxAgeDays
    if body.mfaRequired is not None:
        policy.mfa_required = body.mfaRequired
    if body.maxFailedAttempts is not None:
        policy.max_failed_attempts = body.maxFailedAttempts
    if body.lockoutMinutes is not None:
        policy.lockout_minutes = body.lockoutMinutes
    if body.sessionIdleMinutes is not None:
        policy.session_idle_minutes = body.sessionIdleMinutes
    if body.inactiveUserDays is not None:
        policy.inactive_user_days = body.inactiveUserDays

    audit(tenant_id=actor["tenant_id"], actor_id=actor["user_id"], actor_email=actor["email"], action="auth-policy.updated", entity_type="tenant", entity_id=str(actor["tenant_id"]))
    session.commit()

    return _policy_to_api(policy)


@router.get("/system-roles")
def system_roles(actor: Actor = Depends(require_permission("role:read"))):
    return {"data": [{"name": name, "description": d["description"], "permissions": d["permissions"]} for name, d in SYSTEM_ROLES.items()]}


# ============================================================================
# party types
# ============================================================================


def _slug(s: str) -> str:
    v = re.sub(r"[^a-z0-9]+", "_", s.strip().lower())
    return v.strip("_")[:60]


def _party_type_api(row: PartyType) -> dict:
    return {
        "code": row.code,
        "label": row.label,
        "baseType": row.base_type,
        "status": row.status,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/party-types")
def list_party_types(actor: Actor = Depends(require_permission("party:read")), status: str | None = None):
    q = PartyType.query.filter_by(tenant_id=actor["tenant_id"])
    if status:
        q = q.filter_by(status=status)
    rows = q.order_by(PartyType.label).all()
    return {"data": [_party_type_api(r) for r in rows]}


def _validated_code(body: CreatePartyTypeBody) -> str:
    code = _slug(body.code or body.label)
    if len(code) < 2:
        raise conflict("A party type needs a valid code (letters or digits)", code="PARTY_TYPE_CODE_INVALID")
    return code


def _create_party_type_postgres(tenant_id, body: CreatePartyTypeBody) -> dict:
    code = _validated_code(body)
    if PartyType.query.filter_by(tenant_id=tenant_id, code=code).first():
        raise conflict(f"Party type {code} already exists", code="PARTY_TYPE_TAKEN")

    row = PartyType(tenant_id=tenant_id, code=code, label=body.label, base_type=body.baseType)
    session.add(row)
    session.commit()
    return _party_type_api(row)


def _create_party_type(tenant_id, body: CreatePartyTypeBody) -> dict:
    return _create_party_type_postgres(tenant_id, body)


@router.post("/party-types", status_code=201)
def create_party_type(body: CreatePartyTypeBody, actor: Actor = Depends(require_permission("party:write"))):
    return _create_party_type(actor["tenant_id"], body)


def _patch_party_type_postgres(tenant_id, code: str, body: PatchPartyTypeBody) -> dict:
    row = PartyType.query.filter_by(tenant_id=tenant_id, code=code).first()
    if not row:
        raise not_found("Party type")

    if body.label is not None:
        row.label = body.label
    if body.status is not None:
        row.status = body.status
    session.commit()
    return _party_type_api(row)


def _patch_party_type(tenant_id, code: str, body: PatchPartyTypeBody) -> dict:
    return _patch_party_type_postgres(tenant_id, code, body)


@router.patch("/party-types/{code}")
def patch_party_type(code: str, body: PatchPartyTypeBody, actor: Actor = Depends(require_permission("party:write"))):
    return _patch_party_type(actor["tenant_id"], code, body)


# ============================================================================
# sticker sizes
# ============================================================================

# Standard sheet dimensions (mm) - populated automatically for anything but
# "Custom", so every row is a complete, self-contained print spec (see
# StickerSize.page_width_mm's own docstring).
PAGE_SIZE_MM: dict[str, tuple[Decimal, Decimal]] = {
    "A4": (Decimal("210.00"), Decimal("297.00")),
    "A5": (Decimal("148.00"), Decimal("210.00")),
    "Letter": (Decimal("215.90"), Decimal("279.40")),
}


def _sticker_size_api(row: StickerSize) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "pageSize": row.page_size,
        "pageWidthMm": str(row.page_width_mm),
        "pageHeightMm": str(row.page_height_mm),
        "stickerWidthMm": str(row.sticker_width_mm),
        "stickerHeightMm": str(row.sticker_height_mm),
        "columns": row.columns,
        "rows": row.rows,
        "totalStickersPerPage": row.columns * row.rows,
        "marginLeftMm": str(row.margin_left_mm),
        "marginRightMm": str(row.margin_right_mm),
        "marginTopMm": str(row.margin_top_mm),
        "marginBottomMm": str(row.margin_bottom_mm),
        "gapHorizontalMm": str(row.gap_horizontal_mm),
        "gapVerticalMm": str(row.gap_vertical_mm),
        "status": row.status,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _resolve_page_dims(page_size: str, page_width_mm: str | None, page_height_mm: str | None) -> tuple[Decimal, Decimal]:
    if page_size == "Custom":
        if page_width_mm is None or page_height_mm is None:
            raise rule_violation("Custom page size needs both pageWidthMm and pageHeightMm", code="STICKER_SIZE_INVALID")
        w, h = Decimal(page_width_mm), Decimal(page_height_mm)
        if w <= 0 or h <= 0:
            raise rule_violation("Page width and height must be greater than zero", code="STICKER_SIZE_INVALID")
        return w, h
    return PAGE_SIZE_MM[page_size]


def _assert_layout_fits(*, page_w, page_h, sticker_w, sticker_h, columns, rows, margin_left, margin_right, margin_top, margin_bottom, gap_h, gap_v) -> None:
    needed_w = sticker_w * columns + gap_h * (columns - 1) + margin_left + margin_right
    needed_h = sticker_h * rows + gap_v * (rows - 1) + margin_top + margin_bottom
    if needed_w > page_w:
        raise rule_violation(
            f"{columns} column(s) of {sticker_w}mm stickers with margins and gaps needs {needed_w}mm of width, but the page is only {page_w}mm wide",
            code="STICKER_LAYOUT_INVALID",
        )
    if needed_h > page_h:
        raise rule_violation(
            f"{rows} row(s) of {sticker_h}mm stickers with margins and gaps needs {needed_h}mm of height, but the page is only {page_h}mm tall",
            code="STICKER_LAYOUT_INVALID",
        )


def _assert_name_free(tenant_id, name: str, *, exclude_id: uuid_mod.UUID | None = None) -> None:
    q = StickerSize.query.filter(StickerSize.tenant_id == tenant_id, func.lower(StickerSize.name) == name.lower())
    if exclude_id is not None:
        q = q.filter(StickerSize.id != exclude_id)
    if q.first():
        raise conflict(f'A sticker size template named "{name}" already exists', code="STICKER_SIZE_NAME_TAKEN")


#  GRN & QC calls this to offer the Sticker Size picker when receiving
#  goods - not only the Configuration module itself - so it also accepts
#  warehouse:read. Full CRUD stays behind sticker_size:write.
_STICKER_SIZE_LOOKUP_PERMISSIONS = ("sticker_size:read", "warehouse:read")


@router.get("/sticker-sizes")
def list_sticker_sizes(actor: Actor = Depends(require_any_permission(*_STICKER_SIZE_LOOKUP_PERMISSIONS)), status: str | None = None):
    q = StickerSize.query.filter_by(tenant_id=actor["tenant_id"])
    if status:
        q = q.filter_by(status=status)
    rows = q.order_by(StickerSize.name).all()
    return {"data": [_sticker_size_api(r) for r in rows]}


@router.post("/sticker-sizes", status_code=201)
def create_sticker_size(body: StickerSizeBody, actor: Actor = Depends(require_permission("sticker_size:write"))):
    tenant_id = actor["tenant_id"]

    _assert_name_free(tenant_id, body.name)
    page_w, page_h = _resolve_page_dims(body.pageSize, body.pageWidthMm, body.pageHeightMm)
    sticker_w, sticker_h = Decimal(body.stickerWidthMm), Decimal(body.stickerHeightMm)
    margin_left, margin_right = Decimal(body.marginLeftMm), Decimal(body.marginRightMm)
    margin_top, margin_bottom = Decimal(body.marginTopMm), Decimal(body.marginBottomMm)
    gap_h, gap_v = Decimal(body.gapHorizontalMm), Decimal(body.gapVerticalMm)
    if sticker_w <= 0 or sticker_h <= 0:
        raise rule_violation("Sticker width and height must be greater than zero", code="STICKER_SIZE_INVALID")
    _assert_layout_fits(
        page_w=page_w, page_h=page_h, sticker_w=sticker_w, sticker_h=sticker_h, columns=body.columns, rows=body.rows,
        margin_left=margin_left, margin_right=margin_right, margin_top=margin_top, margin_bottom=margin_bottom, gap_h=gap_h, gap_v=gap_v,
    )

    row = StickerSize(
        tenant_id=tenant_id,
        name=body.name,
        page_size=body.pageSize,
        page_width_mm=page_w,
        page_height_mm=page_h,
        sticker_width_mm=sticker_w,
        sticker_height_mm=sticker_h,
        columns=body.columns,
        rows=body.rows,
        margin_left_mm=margin_left,
        margin_right_mm=margin_right,
        margin_top_mm=margin_top,
        margin_bottom_mm=margin_bottom,
        gap_horizontal_mm=gap_h,
        gap_vertical_mm=gap_v,
        status=body.status,
    )
    session.add(row)
    session.flush()

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="sticker-size.created", entity_type="sticker-size", entity_id=str(row.id), meta={"name": row.name})
    session.commit()
    return _sticker_size_api(row)


@router.patch("/sticker-sizes/{id}")
def patch_sticker_size(id: uuid_mod.UUID, body: PatchStickerSizeBody, actor: Actor = Depends(require_permission("sticker_size:write"))):
    tenant_id = actor["tenant_id"]

    row = StickerSize.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not row:
        raise not_found("Sticker size template")

    if body.name is not None and body.name.lower() != row.name.lower():
        _assert_name_free(tenant_id, body.name, exclude_id=id)

    # Merge onto the row's current values so a partial edit is validated as
    # the *effective* whole template, not just the fields that changed.
    page_size = body.pageSize if body.pageSize is not None else row.page_size
    page_width_mm = body.pageWidthMm if body.pageWidthMm is not None else str(row.page_width_mm)
    page_height_mm = body.pageHeightMm if body.pageHeightMm is not None else str(row.page_height_mm)
    page_w, page_h = _resolve_page_dims(page_size, page_width_mm, page_height_mm)

    sticker_w = Decimal(body.stickerWidthMm) if body.stickerWidthMm is not None else row.sticker_width_mm
    sticker_h = Decimal(body.stickerHeightMm) if body.stickerHeightMm is not None else row.sticker_height_mm
    if sticker_w <= 0 or sticker_h <= 0:
        raise rule_violation("Sticker width and height must be greater than zero", code="STICKER_SIZE_INVALID")
    columns = body.columns if body.columns is not None else row.columns
    rows_ = body.rows if body.rows is not None else row.rows
    margin_left = Decimal(body.marginLeftMm) if body.marginLeftMm is not None else row.margin_left_mm
    margin_right = Decimal(body.marginRightMm) if body.marginRightMm is not None else row.margin_right_mm
    margin_top = Decimal(body.marginTopMm) if body.marginTopMm is not None else row.margin_top_mm
    margin_bottom = Decimal(body.marginBottomMm) if body.marginBottomMm is not None else row.margin_bottom_mm
    gap_h = Decimal(body.gapHorizontalMm) if body.gapHorizontalMm is not None else row.gap_horizontal_mm
    gap_v = Decimal(body.gapVerticalMm) if body.gapVerticalMm is not None else row.gap_vertical_mm

    _assert_layout_fits(
        page_w=page_w, page_h=page_h, sticker_w=sticker_w, sticker_h=sticker_h, columns=columns, rows=rows_,
        margin_left=margin_left, margin_right=margin_right, margin_top=margin_top, margin_bottom=margin_bottom, gap_h=gap_h, gap_v=gap_v,
    )

    row.name = body.name if body.name is not None else row.name
    row.page_size = page_size
    row.page_width_mm = page_w
    row.page_height_mm = page_h
    row.sticker_width_mm = sticker_w
    row.sticker_height_mm = sticker_h
    row.columns = columns
    row.rows = rows_
    row.margin_left_mm = margin_left
    row.margin_right_mm = margin_right
    row.margin_top_mm = margin_top
    row.margin_bottom_mm = margin_bottom
    row.gap_horizontal_mm = gap_h
    row.gap_vertical_mm = gap_v
    if body.status is not None:
        row.status = body.status

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="sticker-size.updated", entity_type="sticker-size", entity_id=str(id), meta={"name": row.name})
    session.commit()
    return _sticker_size_api(row)


@router.delete("/sticker-sizes/{id}", status_code=204)
def delete_sticker_size(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("sticker_size:write"))):
    tenant_id = actor["tenant_id"]
    row = StickerSize.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not row:
        raise not_found("Sticker size template")

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="sticker-size.deleted", entity_type="sticker-size", entity_id=str(id), meta={"name": row.name})
    session.delete(row)
    session.commit()
    return Response(status_code=204)
