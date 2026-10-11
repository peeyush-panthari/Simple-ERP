"""Product categories and business entities. Ported 1:1 (behavior) from
backend_py/app/routes/{product_categories,business_entities}.py. The
in-process category cache the original invalidates on writes doesn't exist
in this port (load_categories always reads the DB), so those calls are
simply gone."""

from __future__ import annotations

import csv
import io
import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from pydantic import ValidationError
from sqlalchemy import func, or_

from app.core.audit import audit
from app.core.auth import Actor, require_any_permission, require_permission
from app.core.config import settings
from app.core.db import session
from app.core.errors import ProblemError, conflict, not_found, rule_violation
from app.core.pagination import ListQuery, list_response, offset_of
from app.domains.foundation.schemas import (
    BulkUploadBody,
    BusinessEntityBody,
    CategoryBody,
    PatchBusinessEntityBody,
    PatchCategoryBody,
)
from app.models.business_entity import BusinessEntity
from app.models.product import Product
from app.models.product_category import ProductCategory
from app.services import product_repo
from app.services.org_repo import to_business_entity_api
from app.services.party_tax_id import assert_valid_tax_id
from app.services.product_category import resolve_ancestry
from app.services.sequences import next_business_entity_code, next_category_code

router = APIRouter(prefix="/api/v1", tags=["foundation"])


# ============================================================================
# product categories
# ============================================================================


@router.get("/product-categories")
def list_categories(actor: Actor = Depends(require_permission("product:read")), query: ListQuery = Depends(), status: str | None = None):
    q = ProductCategory.query.filter(ProductCategory.tenant_id == actor["tenant_id"])
    if status:
        q = q.filter(ProductCategory.status == status)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(ProductCategory.code.ilike(like), ProductCategory.product_category.ilike(like)))

    total = q.count()
    rows = q.order_by(ProductCategory.code).limit(query.limit).offset(offset_of(query)).all()

    # One grouped count for the page, not one count query per category.
    product_counts = (
        dict(session.query(Product.category_id, func.count()).filter(Product.category_id.in_([r.id for r in rows])).group_by(Product.category_id).all())
        if rows
        else {}
    )

    data = []
    for r in rows:
        api = product_repo.to_category_api(r)
        api["productCount"] = product_counts.get(r.id, 0)
        data.append(api)

    return list_response(data, query, total)


@router.get("/product-categories/tree")
def category_tree(actor: Actor = Depends(require_permission("product:read"))):
    categories = product_repo.load_categories(actor["tenant_id"])
    by_parent: dict[str | None, list[str]] = {}
    for node in categories.values():
        by_parent.setdefault(node.parent_id, []).append(node.id)

    def build(parent_id: str | None, depth: int) -> list[dict]:
        if depth > settings.category_max_depth:
            return []
        ids = sorted(by_parent.get(parent_id, []), key=lambda i: categories[i].code)
        return [
            {
                "id": categories[i].id,
                "code": categories[i].code,
                "productCategory": categories[i].product_category,
                "requiresBatch": categories[i].requires_batch,
                "requiresExpiry": categories[i].requires_expiry,
                "productTypes": categories[i].product_types,
                "status": categories[i].status,
                "children": build(i, depth + 1),
            }
            for i in ids
        ]

    return {"data": build(None, 1)}


def _assert_parent_depth_ok(tenant_id, parent_id) -> None:
    categories = product_repo.load_categories(tenant_id)
    if str(parent_id) not in categories:
        raise not_found("Parent category")
    ancestry = resolve_ancestry(str(parent_id), categories, settings.category_max_depth)
    if len(ancestry) >= settings.category_max_depth:
        raise rule_violation(
            f"Adding a child under {' → '.join(c.code for c in ancestry)} would exceed the maximum depth of {settings.category_max_depth}",
            code="CATEGORY_TOO_DEEP",
        )


def _assert_code_free(tenant_id, code: str) -> None:
    if ProductCategory.query.filter(ProductCategory.tenant_id == tenant_id, func.upper(ProductCategory.code) == code.upper()).first():
        raise conflict(f"Category code {code} is already in use", code="CATEGORY_CODE_TAKEN")


def _create_category_postgres(tenant_id, actor: dict, body: CategoryBody) -> dict:
    if body.parentId:
        _assert_parent_depth_ok(tenant_id, body.parentId)

    code = body.code or next_category_code(tenant_id)
    _assert_code_free(tenant_id, code)

    row = ProductCategory(
        tenant_id=tenant_id,
        code=code,
        product_category=body.productCategory,
        parent_id=body.parentId,
        product_types=body.productTypes,
        requires_batch=body.requiresBatch,
        requires_expiry=body.requiresExpiry,
        default_tax_code=body.defaultTaxCode,
        status=body.status,
    )
    session.add(row)
    session.flush()

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="product-category.created", entity_type="product-category", entity_id=str(row.id))
    product_repo.invalidate_category_cache()
    session.commit()
    return product_repo.to_category_api(row)


def _create_category(tenant_id, actor: dict, body: CategoryBody) -> dict:
    return _create_category_postgres(tenant_id, actor, body)


@router.post("/product-categories", status_code=201)
def create_category(body: CategoryBody, actor: Actor = Depends(require_permission("product:write"))):
    return _create_category(actor["tenant_id"], actor, body)


def _assert_reparent_ok(tenant_id, id: uuid_mod.UUID, row: ProductCategory, new_parent_id) -> None:
    if new_parent_id == id:
        raise rule_violation("A category cannot be its own parent", code="CATEGORY_CYCLE")
    categories = product_repo.load_categories(tenant_id)
    # Simulate the reparent before committing: walking the *proposed* tree is
    # the only way to catch "move a parent under its own descendant".
    node = product_repo.to_category_node(row)
    node.parent_id = str(new_parent_id) if new_parent_id else None
    categories[str(id)] = node
    resolve_ancestry(str(id), categories, settings.category_max_depth)


# column name on the model <- attribute name on the patch body
_PATCH_COLUMNS = {
    "code": "code",
    "product_category": "productCategory",
    "parent_id": "parentId",
    "product_types": "productTypes",
    "requires_batch": "requiresBatch",
    "requires_expiry": "requiresExpiry",
    "default_tax_code": "defaultTaxCode",
    "status": "status",
}
# These two are explicitly nullable: "sent as null" has to be distinguishable
# from "not sent", so they key off model_fields_set rather than `is not None`.
_NULLABLE_PATCH_FIELDS = {"parentId", "defaultTaxCode"}


def _patch_set_values(body: PatchCategoryBody) -> dict:
    fields_set = body.model_fields_set
    set_values = {}
    for column, field in _PATCH_COLUMNS.items():
        value = getattr(body, field)
        if field in _NULLABLE_PATCH_FIELDS:
            if field in fields_set:
                set_values[column] = value
        elif value is not None:
            set_values[column] = value
    return set_values


def _patch_category_postgres(tenant_id, actor: dict, id: uuid_mod.UUID, body: PatchCategoryBody) -> dict:
    row = ProductCategory.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not row:
        raise not_found("Product category")

    if "parentId" in body.model_fields_set and body.parentId != row.parent_id:
        _assert_reparent_ok(tenant_id, id, row, body.parentId)

    for column, value in _patch_set_values(body).items():
        setattr(row, column, value)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="product-category.updated", entity_type="product-category", entity_id=str(id))
    product_repo.invalidate_category_cache()
    session.commit()
    return product_repo.to_category_api(row)


def _patch_category(tenant_id, actor: dict, id: uuid_mod.UUID, body: PatchCategoryBody) -> dict:
    return _patch_category_postgres(tenant_id, actor, id, body)


@router.patch("/product-categories/{id}")
def patch_category(id: uuid_mod.UUID, body: PatchCategoryBody, actor: Actor = Depends(require_permission("product:write"))):
    return _patch_category(actor["tenant_id"], actor, id, body)


def _assert_category_unused(id: uuid_mod.UUID) -> None:
    products_count = Product.query.filter_by(category_id=id).count()
    children_count = ProductCategory.query.filter_by(parent_id=id).count()
    if products_count > 0 or children_count > 0:
        raise conflict(
            f"This category still holds {products_count} product(s) and {children_count} sub-categor(ies) — move them first, or set the category inactive instead",
            code="CATEGORY_IN_USE",
        )


def _delete_category_postgres(tenant_id, actor: dict, id: uuid_mod.UUID) -> None:
    _assert_category_unused(id)

    row = ProductCategory.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not row:
        raise not_found("Product category")

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="product-category.deleted", entity_type="product-category", entity_id=str(id))
    session.delete(row)
    product_repo.invalidate_category_cache()
    session.commit()


def _delete_category(tenant_id, actor: dict, id: uuid_mod.UUID) -> None:
    _delete_category_postgres(tenant_id, actor, id)


@router.delete("/product-categories/{id}", status_code=204)
def delete_category(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("product:write"))):
    """Categories referenced by products or child categories are never deleted."""
    _delete_category(actor["tenant_id"], actor, id)
    return Response(status_code=204)


# ============================================================================
# business entities
# ============================================================================


def _unset_other_defaults(tenant_id, keep_id=None) -> None:
    q = BusinessEntity.query.filter_by(tenant_id=tenant_id, is_default=True)
    if keep_id:
        q = q.filter(BusinessEntity.id != keep_id)
    q.update({"is_default": False})


#  Procurement calls this list endpoint directly to show which of our own
#  legal entities a PO is issued from - not only the PO & Invoice module
#  itself - so it also accepts po:read. Full CRUD stays behind org:write.
_BUSINESS_ENTITY_LOOKUP_PERMISSIONS = ("org:read", "po:read")


@router.get("/business-entities")
def list_business_entities(actor: Actor = Depends(require_any_permission(*_BUSINESS_ENTITY_LOOKUP_PERMISSIONS)), query: ListQuery = Depends(), status: str | None = None):
    q = BusinessEntity.query.filter(BusinessEntity.tenant_id == actor["tenant_id"])
    if status:
        q = q.filter(BusinessEntity.status == status)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(BusinessEntity.code.ilike(like), BusinessEntity.name.ilike(like)))

    total = q.count()
    rows = q.order_by(BusinessEntity.code).limit(query.limit).offset(offset_of(query)).all()
    return list_response([to_business_entity_api(r) for r in rows], query, total)


def _create_business_entity_postgres(tenant_id, actor: dict, body: BusinessEntityBody) -> dict:
    tax = assert_valid_tax_id(body.taxId, body.taxIdCountry or body.country, validate=False) if body.taxId else None

    code = body.code or next_business_entity_code(tenant_id)
    if BusinessEntity.query.filter(BusinessEntity.tenant_id == tenant_id, func.upper(BusinessEntity.code) == code.upper()).first():
        raise conflict(f"Code {code} is already in use", code="BUSINESS_ENTITY_CODE_TAKEN")

    is_first = BusinessEntity.query.filter_by(tenant_id=tenant_id).count() == 0
    make_default = body.isDefault or is_first

    row = BusinessEntity(
        tenant_id=tenant_id,
        code=code,
        name=body.name,
        address_line1=body.addressLine1,
        address_line2=body.addressLine2,
        city=body.city,
        state_code=body.stateCode,
        postal_code=body.postalCode,
        country=body.country,
        tax_id=tax.tax_id if tax else None,
        tax_id_country=tax.country if tax else None,
        pan=body.pan,
        contact_email=body.contactEmail,
        contact_phone=body.contactPhone,
        bank_name=body.bankName,
        bank_branch=body.bankBranch,
        bank_account_number=body.bankAccountNumber,
        bank_ifsc=body.bankIfsc,
        is_default=make_default,
        status=body.status,
    )
    session.add(row)
    session.flush()

    if make_default:
        _unset_other_defaults(tenant_id, keep_id=row.id)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="business-entity.created", entity_type="business-entity", entity_id=str(row.id))
    session.commit()
    return to_business_entity_api(row)


def _create_business_entity(tenant_id, actor: dict, body: BusinessEntityBody) -> dict:
    """Shared by the single create route and the bulk-upload route, so an
    entity created either way goes through the exact same code numbering,
    default-flag handling and audit trail."""
    return _create_business_entity_postgres(tenant_id, actor, body)


@router.post("/business-entities", status_code=201)
def create_business_entity(body: BusinessEntityBody, actor: Actor = Depends(require_permission("org:write"))):
    return _create_business_entity(actor["tenant_id"], actor, body)


ENTITY_BULK_UPLOAD_REQUIRED_COLUMNS = ["name"]


def _parse_bool(value: str, default: bool) -> bool:
    v = (value or "").strip().lower()
    if v in ("true", "1", "yes", "y"):
        return True
    if v in ("false", "0", "no", "n"):
        return False
    return default


@router.post("/business-entities/bulk-upload")
def bulk_upload_business_entities(body: BulkUploadBody, actor: Actor = Depends(require_permission("org:write"))):
    """Creates many business entities from one CSV in a single request - one
    row per entity. A bad row is reported as an error and skipped, it never
    fails rows that already validated fine."""
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in ENTITY_BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    results = []
    for row_number, raw_row in enumerate(reader, start=2):  # header is row 1
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k}
        if not any(row.values()):
            continue
        label = row.get("name") or f"(row {row_number})"

        try:
            create_body = BusinessEntityBody(
                code=row.get("code") or None,
                name=row.get("name") or "",
                addressLine1=row.get("addressLine1") or None,
                addressLine2=row.get("addressLine2") or None,
                city=row.get("city") or None,
                stateCode=row.get("stateCode") or None,
                postalCode=row.get("postalCode") or None,
                country=row.get("country") or "IN",
                taxId=row.get("taxId") or None,
                taxIdCountry=row.get("taxIdCountry") or None,
                pan=row.get("pan") or None,
                contactEmail=row.get("contactEmail") or None,
                contactPhone=row.get("contactPhone") or None,
                bankName=row.get("bankName") or None,
                bankBranch=row.get("bankBranch") or None,
                bankAccountNumber=row.get("bankAccountNumber") or None,
                bankIfsc=row.get("bankIfsc") or None,
                isDefault=_parse_bool(row.get("isDefault", ""), False),
                status=row.get("status") or "active",
            )
        except ValidationError as exc:
            results.append({"row": row_number, "name": label, "status": "error", "error": exc.errors()[0].get("msg", "invalid data"), "rowData": row})
            continue

        try:
            entity = _create_business_entity(tenant_id, actor, create_body)
            results.append({"row": row_number, "name": label, "status": "success", "code": entity["code"], "rowData": row})
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


@router.patch("/business-entities/{id}")
def patch_business_entity(id: uuid_mod.UUID, body: PatchBusinessEntityBody, actor: Actor = Depends(require_permission("org:write"))):
    tenant_id = actor["tenant_id"]

    row = BusinessEntity.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not row:
        raise not_found("Business entity")

    if body.code is not None:
        if BusinessEntity.query.filter(BusinessEntity.tenant_id == tenant_id, BusinessEntity.id != id, func.upper(BusinessEntity.code) == body.code.upper()).first():
            raise conflict(f"Code {body.code} is already in use", code="BUSINESS_ENTITY_CODE_TAKEN")
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
    if "taxId" in body.model_fields_set:
        if body.taxId:
            tax = assert_valid_tax_id(body.taxId, body.taxIdCountry or row.tax_id_country or row.country, validate=False)
            row.tax_id = tax.tax_id
            row.tax_id_country = tax.country
        else:
            row.tax_id = None
            row.tax_id_country = None
    if "pan" in body.model_fields_set:
        row.pan = body.pan
    if "contactEmail" in body.model_fields_set:
        row.contact_email = body.contactEmail
    if "contactPhone" in body.model_fields_set:
        row.contact_phone = body.contactPhone
    if "bankName" in body.model_fields_set:
        row.bank_name = body.bankName
    if "bankBranch" in body.model_fields_set:
        row.bank_branch = body.bankBranch
    if "bankAccountNumber" in body.model_fields_set:
        row.bank_account_number = body.bankAccountNumber
    if "bankIfsc" in body.model_fields_set:
        row.bank_ifsc = body.bankIfsc
    if body.status is not None:
        row.status = body.status
    if body.isDefault is not None:
        row.is_default = body.isDefault
        if body.isDefault:
            _unset_other_defaults(tenant_id, keep_id=id)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="business-entity.updated", entity_type="business-entity", entity_id=str(id))
    session.commit()

    return to_business_entity_api(row)
