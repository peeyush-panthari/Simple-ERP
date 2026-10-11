"""Products: CRUD, publish/deprecate/convert, conversions/aliases/images/specs.
Ported 1:1 (behavior) from backend_py/app/routes/products.py."""

from __future__ import annotations

import csv
import io
import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import or_

from app.core.auth import Actor, require_any_permission, require_permission
from app.core.audit import audit
from app.core.config import settings
from app.core.db import session
from app.core.errors import ProblemError, conflict, not_found, rule_violation
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.money import decimal_str
from app.core.pagination import ListQuery, list_response, offset_of
from app.domains.products.schemas import (
    AddAliasBody,
    AddImageBody,
    AddSpecBody,
    ConvertBody,
    CreateProductBody,
    DeprecateBody,
    PatchProductBody,
    ProductBulkUploadBody,
    SetConversionBody,
)
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.models.product_category import ProductCategory
from app.models.product_image import ProductImage
from app.models.product_spec import ProductSpec
from app.models.uom_conversion import UomConversion
from app.services import bom_repo, product_repo
from app.services.product_category import assert_category_compliance, effective_rules, resolve_ancestry
from app.services.product_conversion import ProductConversion, assert_conversion_consistent, resolve_conversion
from app.services.product_publish import PublishCandidate, assert_publishable
from app.services.product_sku import SkuChangeContext, assert_sku_change_allowed, assert_uom_change_allowed, assert_valid_sku
from app.services.sequences import next_sku

router = APIRouter(prefix="/api/v1", tags=["products"])

_SORTABLE = {
    "sku": Product.sku,
    "name": Product.name,
    "type": Product.type,
    "status": Product.status,
    "created_at": Product.created_at,
    "updated_at": Product.updated_at,
}

#  Inventory, Production, Orders, Procurement all call this list endpoint
#  directly for display purposes - not only the Products & BOM module itself.
_PRODUCT_LOOKUP_PERMISSIONS = ("product:read", "inventory:read", "order:read", "po:read", "pr:read")


def _category_rules_for(tenant_id, category_id: uuid_mod.UUID | None):
    if not category_id:
        return None
    categories = product_repo.load_categories(tenant_id)
    if str(category_id) not in categories:
        raise not_found("Product category")
    return effective_rules(resolve_ancestry(str(category_id), categories, settings.category_max_depth))


@router.get("/products")
def list_products(
    actor: Actor = Depends(require_any_permission(*_PRODUCT_LOOKUP_PERMISSIONS)),
    query: ListQuery = Depends(),
    type: str | None = None,
    status: str | None = None,
    categoryId: uuid_mod.UUID | None = None,
    purchasable: bool | None = None,
    sellable: bool | None = None,
):
    q = Product.query.filter(Product.tenant_id == actor["tenant_id"])
    if type:
        q = q.filter(Product.type == type)
    if status:
        q = q.filter(Product.status == status)
    if categoryId:
        q = q.filter(Product.category_id == categoryId)
    if purchasable is not None:
        q = q.filter(Product.purchasable == purchasable)
    if sellable is not None:
        q = q.filter(Product.sellable == sellable)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(Product.sku.ilike(like), Product.name.ilike(like)))

    total = q.count()
    sort_col = _SORTABLE.get((query.sort or "").lstrip("-"), Product.sku)
    order = sort_col.desc() if (query.sort or "").startswith("-") else sort_col.asc()
    rows = q.order_by(order).limit(query.limit).offset(offset_of(query)).all()

    categories = product_repo.load_categories(actor["tenant_id"])
    data = []
    for r in rows:
        api = product_repo.to_product_api(r)
        cat = categories.get(str(r.category_id)) if r.category_id else None
        api["categoryName"] = cat.product_category if cat else None
        data.append(api)

    return list_response(data, query, total)


@router.get("/products/{id}")
def get_product(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("product:read"))):
    tenant_id = actor["tenant_id"]
    product = product_repo.require_product(tenant_id, id)
    images = ProductImage.query.filter_by(product_id=id).order_by(ProductImage.sort_order, ProductImage.created_at).all()
    specs = ProductSpec.query.filter_by(product_id=id).order_by(ProductSpec.sort_order, ProductSpec.key).all()
    conversions = product_repo.load_conversions(id)
    aliases = ProductAlias.query.filter_by(product_id=id).order_by(ProductAlias.created_at).all()

    categories = product_repo.load_categories(tenant_id)
    ancestry = resolve_ancestry(str(product.category_id), categories, settings.category_max_depth) if product.category_id else []

    result = product_repo.to_product_api(product)
    result["categoryBreadcrumb"] = [{"id": c.id, "code": c.code, "name": c.product_category} for c in ancestry]
    rules = effective_rules(ancestry) if ancestry else None
    result["categoryRules"] = (
        {
            "requiresBatch": rules.requires_batch,
            "requiresExpiry": rules.requires_expiry,
            "allowedProductTypes": rules.allowed_product_types,
            "defaultTaxCode": rules.default_tax_code,
            "breadcrumb": rules.breadcrumb,
        }
        if rules
        else None
    )
    result["images"] = [product_repo.to_image_api(i) for i in images]
    result["specs"] = [product_repo.to_spec_api(s) for s in specs]
    result["conversions"] = conversions
    result["aliases"] = [{"id": str(a.id), "aliasSku": a.alias_sku, "reason": a.reason} for a in aliases]
    return result


def _create_product(tenant_id, actor: Actor, body: CreateProductBody) -> Product:
    """Shared by the single-product create route and the bulk-upload route."""
    sku = assert_valid_sku(body.sku) if body.sku else next_sku(tenant_id, body.type)
    existing = product_repo.find_by_sku(tenant_id, sku)
    if existing:
        suffix = f" (as an alias of {existing.sku})" if existing.sku != sku else ""
        raise conflict(f'SKU {sku} already belongs to "{existing.name}"{suffix}', code="SKU_TAKEN")

    name_make_owner = product_repo.find_by_name_and_make(tenant_id, body.name, body.make)
    if name_make_owner:
        raise conflict(
            f'A product named "{body.name}" with make "{body.make}" already exists ({name_make_owner.sku})',
            code="PRODUCT_NAME_MAKE_TAKEN",
        )

    rules = _category_rules_for(tenant_id, body.categoryId)
    if rules:
        assert_category_compliance(
            sku=sku,
            type=body.type,
            batch_tracked=body.batchTracked or rules.requires_batch,
            expiry_tracked=body.expiryTracked or rules.requires_expiry,
            rules=rules,
        )

    now = datetime.now(timezone.utc)
    product = Product(
        tenant_id=tenant_id,
        sku=sku,
        name=body.name,
        make=body.make,
        model_number=body.modelNumber,
        description=body.description,
        type=body.type,
        category_id=body.categoryId,
        uom=body.uom,
        alternate_uoms=body.alternateUoms,
        hsn_code=body.hsnCode,
        batch_tracked=body.batchTracked or bool(rules and rules.requires_batch),
        expiry_tracked=body.expiryTracked or bool(rules and rules.requires_expiry),
        storage_conditions=body.storageConditions,
        reorder_point=body.reorderPoint,
        reorder_qty=body.reorderQty,
        lead_time_days=body.leadTimeDays,
        currency=body.currency or settings.base_currency,
        purchasable=body.purchasable,
        sellable=body.sellable,
        weight_kg=body.weightKg,
        volume_m3=body.volumeM3,
        # Publish flow removed: products are active (published) on creation - faithful port.
        status="active",
        published_at=now,
    )
    session.add(product)
    session.flush()

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="product.created", entity_type="product", entity_id=str(product.id))
    session.commit()
    return product


@router.post("/products", status_code=201)
def create_product(body: CreateProductBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("product:write"))):
    if not body.sku:
        raise rule_violation("SKU ID is required", code="SKU_REQUIRED")
    tenant_id = actor["tenant_id"]

    def _do():
        product = _create_product(tenant_id, actor, body)
        return 201, product_repo.to_product_api(product)

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


BULK_UPLOAD_REQUIRED_COLUMNS = ["name", "make", "type", "categoryCode", "uom"]


def _parse_bool(value: str, default: bool) -> bool:
    v = (value or "").strip().lower()
    if v in ("true", "1", "yes", "y"):
        return True
    if v in ("false", "0", "no", "n"):
        return False
    return default


@router.post("/products/bulk-upload")
def bulk_upload_products(body: ProductBulkUploadBody, actor: Actor = Depends(require_permission("product:write"))):
    """Creates many products from one CSV in a single request - one row per product."""
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    parsed = [
        (row_number, {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k})
        for row_number, raw_row in enumerate(reader, start=2)
    ]
    wanted_categories = {r.get("categoryCode") for _, r in parsed if r.get("categoryCode")}
    categories_by_code = (
        {c.code: c for c in ProductCategory.query.filter(ProductCategory.tenant_id == tenant_id, ProductCategory.code.in_(wanted_categories)).all()}
        if wanted_categories
        else {}
    )

    results = []
    for row_number, row in parsed:
        if not any(row.values()):
            continue
        label = row.get("name") or f"(row {row_number})"

        category_code = row.get("categoryCode") or ""
        category = categories_by_code.get(category_code) if category_code else None
        errors: list[str] = []
        if not category_code:
            errors.append("categoryCode is required")
        elif not category:
            errors.append(f"Category code '{category_code}' not found")

        product_type = row.get("type") or ""
        sellable_default = product_type == "finished_good"

        if errors:
            results.append({"row": row_number, "name": label, "status": "error", "error": "; ".join(errors), "rowData": row})
            continue

        try:
            create_body = CreateProductBody(
                sku=row.get("sku") or None,
                name=row.get("name") or "",
                make=row.get("make") or "",
                modelNumber=row.get("modelNumber") or None,
                description=row.get("description") or None,
                type=product_type,
                categoryId=category.id,
                uom=row.get("uom") or "",
                hsnCode=row.get("hsnCode") or None,
                batchTracked=_parse_bool(row.get("batchTracked", ""), False),
                expiryTracked=_parse_bool(row.get("expiryTracked", ""), False),
                storageConditions=row.get("storageConditions") or None,
                reorderPoint=row.get("reorderPoint") or None,
                reorderQty=row.get("reorderQty") or None,
                leadTimeDays=int(row["leadTimeDays"]) if row.get("leadTimeDays") else None,
                currency=row.get("currency") or None,
                purchasable=_parse_bool(row.get("purchasable", ""), True),
                sellable=_parse_bool(row.get("sellable", ""), sellable_default),
                weightKg=row.get("weightKg") or None,
                volumeM3=row.get("volumeM3") or None,
            )
        except (ValidationError, ValueError) as exc:
            message = exc.errors()[0].get("msg", "invalid product data") if isinstance(exc, ValidationError) else str(exc)
            results.append({"row": row_number, "name": label, "status": "error", "error": message, "rowData": row})
            continue

        try:
            product = _create_product(tenant_id, actor, create_body)
            results.append({"row": row_number, "name": label, "status": "success", "sku": product.sku, "rowData": row})
        except ProblemError as exc:
            session.rollback()
            results.append({"row": row_number, "name": label, "status": "error", "error": exc.detail, "rowData": row})
        except Exception as exc:  # noqa: BLE001 - one bad row must not fail the whole batch
            session.rollback()
            results.append({"row": row_number, "name": label, "status": "error", "error": str(exc), "rowData": row})

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    return {
        "summary": {"totalRows": len(results), "successCount": success_count, "errorCount": error_count},
        "results": [
            {
                "row": r["row"],
                "name": r["name"],
                "status": r["status"],
                "sku": r.get("sku"),
                "error": r.get("error"),
                "rowData": r["rowData"] if r["status"] == "error" else {},
            }
            for r in results
        ],
    }


@router.patch("/products/{id}")
def patch_product(id: uuid_mod.UUID, body: PatchProductBody, actor: Actor = Depends(require_permission("product:write"))):
    tenant_id = actor["tenant_id"]
    before = product_repo.require_product(tenant_id, id)
    fields_set = body.model_fields_set

    ctx = SkuChangeContext(current_sku=before.sku, status=before.status, first_transaction_at=before.first_transaction_at, first_transaction_ref=before.first_transaction_ref)
    sku = assert_valid_sku(body.sku) if body.sku else before.sku
    if body.sku:
        assert_sku_change_allowed(ctx, sku)
    if body.uom:
        assert_uom_change_allowed(ctx, before.uom, body.uom)

    if body.name is not None or body.make is not None:
        new_name = body.name if body.name is not None else before.name
        new_make = body.make if body.make is not None else (before.make or "")
        name_make_owner = product_repo.find_by_name_and_make(tenant_id, new_name, new_make, exclude_id=id)
        if name_make_owner:
            raise conflict(
                f'A product named "{new_name}" with make "{new_make}" already exists ({name_make_owner.sku})',
                code="PRODUCT_NAME_MAKE_TAKEN",
            )

    category_id = body.categoryId if "categoryId" in fields_set else before.category_id
    rules = _category_rules_for(tenant_id, category_id)
    if rules:
        assert_category_compliance(
            sku=sku,
            type=body.type or before.type,
            batch_tracked=body.batchTracked if body.batchTracked is not None else before.batch_tracked,
            expiry_tracked=body.expiryTracked if body.expiryTracked is not None else before.expiry_tracked,
            rules=rules,
        )

    before.sku = sku
    if body.name is not None:
        before.name = body.name
    if body.make is not None:
        before.make = body.make
    if "modelNumber" in fields_set:
        before.model_number = body.modelNumber
    if "description" in fields_set:
        before.description = body.description
    if body.type is not None:
        before.type = body.type
    if "categoryId" in fields_set:
        before.category_id = body.categoryId
    if body.uom is not None:
        before.uom = body.uom
    if body.alternateUoms is not None:
        before.alternate_uoms = body.alternateUoms
    if "hsnCode" in fields_set:
        before.hsn_code = body.hsnCode
    if body.batchTracked is not None:
        before.batch_tracked = body.batchTracked
    if body.expiryTracked is not None:
        before.expiry_tracked = body.expiryTracked
    if "storageConditions" in fields_set:
        before.storage_conditions = body.storageConditions
    if "reorderPoint" in fields_set:
        before.reorder_point = body.reorderPoint
    if "reorderQty" in fields_set:
        before.reorder_qty = body.reorderQty
    if "leadTimeDays" in fields_set:
        before.lead_time_days = body.leadTimeDays
    if body.currency is not None:
        before.currency = body.currency
    if body.purchasable is not None:
        before.purchasable = body.purchasable
    if body.sellable is not None:
        before.sellable = body.sellable
    if "weightKg" in fields_set:
        before.weight_kg = body.weightKg
    if "volumeM3" in fields_set:
        before.volume_m3 = body.volumeM3

    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="product.updated",
        entity_type="product",
        entity_id=str(id),
        reason=body.reason,
    )
    session.commit()

    return product_repo.to_product_api(before)


@router.post("/products/{id}/publish")
def publish_product(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("product:publish"))):
    tenant_id = actor["tenant_id"]
    product = product_repo.require_product(tenant_id, id)

    bom_ok = bom_repo.has_approved_bom(tenant_id, id) if product.type == "finished_good" and product.sellable else None

    assert_publishable(
        PublishCandidate(
            sku=product.sku,
            name=product.name,
            type=product.type,
            category_id=str(product.category_id) if product.category_id else None,
            uom=product.uom,
            status=product.status,
            image_count=product_repo.count_images(id),
            spec_count=product_repo.count_specs(id),
            sellable=product.sellable,
            has_approved_bom=bom_ok,
        )
    )

    if product.published_at is None:
        product.published_at = datetime.now(timezone.utc)
    product.status = "active"

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="product.published", entity_type="product", entity_id=str(id))
    session.commit()

    return product_repo.to_product_api(product)


@router.post("/products/{id}/deprecate")
def deprecate_product(id: uuid_mod.UUID, body: DeprecateBody, actor: Actor = Depends(require_permission("product:publish"))):
    tenant_id = actor["tenant_id"]
    product = product_repo.require_product(tenant_id, id)
    if product.status == "deprecated":
        raise conflict(f"{product.sku} is already deprecated", code="PRODUCT_ALREADY_DEPRECATED")

    # procurement/order open-document counts aren't wired up yet (see the
    # migration plan) - both report "unknown", the same tri-state semantics
    # the original preserves for "sibling unreachable". force=True is
    # required to deprecate until those checks land for real.
    counts = [{"service": "procurement", "openCount": None}, {"service": "order", "openCount": None}]
    blocking = [c for c in counts if (c["openCount"] or 0) > 0]
    unknown = [c for c in counts if c["openCount"] is None]

    if blocking:
        raise rule_violation(
            f"{product.sku} still appears on open documents ({', '.join(f'{c['openCount']} in {c['service']}' for c in blocking)}). Close or cancel them first",
            code="PRODUCT_IN_USE",
            meta={"counts": counts},
        )
    if unknown and not body.force:
        raise rule_violation(
            f"Could not confirm whether {product.sku} is on open documents ({', '.join(c['service'] for c in unknown)} unreachable). "
            "Retry later, or resend with force=true to deprecate anyway — the override is recorded in the audit trail",
            code="OPEN_DOCUMENT_CHECK_UNAVAILABLE",
            meta={"counts": counts},
        )

    product.status = "deprecated"
    product.deprecated_at = datetime.now(timezone.utc)
    product.deprecated_reason = body.reason
    product.purchasable = False
    product.sellable = False

    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="product.deprecated",
        entity_type="product",
        entity_id=str(id),
        reason=body.reason,
        meta={"forced": body.force and len(unknown) > 0, "unreachable": [c["service"] for c in unknown]},
    )
    session.commit()

    return product_repo.to_product_api(product)


@router.post("/products/{id}/convert")
def convert_product(id: uuid_mod.UUID, body: ConvertBody, actor: Actor = Depends(require_permission("product:read"))):
    product_repo.require_product(actor["tenant_id"], id)
    conversions = [ProductConversion(from_uom=c["fromUom"], to_uom=c["toUom"], factor=c["factor"]) for c in product_repo.load_conversions(id)]
    result = resolve_conversion(body.quantity, body.from_.upper(), body.to.upper(), conversions)
    return {"quantity": body.quantity, "from": body.from_.upper(), "to": body.to.upper(), "result": decimal_str(result)}


@router.post("/products/{id}/conversions", status_code=201)
def add_conversion(id: uuid_mod.UUID, body: SetConversionBody, actor: Actor = Depends(require_permission("product:write"))):
    tenant_id = actor["tenant_id"]
    product_repo.require_product(tenant_id, id)
    existing = [ProductConversion(from_uom=c["fromUom"], to_uom=c["toUom"], factor=c["factor"]) for c in product_repo.load_conversions(id)]
    candidate = ProductConversion(from_uom=body.fromUom, to_uom=body.toUom, factor=body.factor)
    assert_conversion_consistent(candidate, existing)

    row = UomConversion.query.filter_by(product_id=id, from_uom=body.fromUom, to_uom=body.toUom).first()
    if row:
        row.factor = body.factor
    else:
        session.add(UomConversion(tenant_id=tenant_id, product_id=id, from_uom=body.fromUom, to_uom=body.toUom, factor=body.factor))

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="product.conversion.set", entity_type="product", entity_id=str(id))
    session.commit()

    return {"productId": str(id), "conversions": product_repo.load_conversions(id)}


@router.post("/products/{id}/aliases", status_code=201)
def add_alias(id: uuid_mod.UUID, body: AddAliasBody, actor: Actor = Depends(require_permission("product:write"))):
    tenant_id = actor["tenant_id"]
    product = product_repo.require_product(tenant_id, id)
    alias = assert_valid_sku(body.aliasSku)
    clash = product_repo.find_by_sku(tenant_id, alias)
    if clash:
        raise conflict(f"{alias} already resolves to {clash.sku}", code="SKU_TAKEN")

    session.add(ProductAlias(tenant_id=tenant_id, product_id=id, alias_sku=alias, reason=body.reason))
    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="product.alias.added",
        entity_type="product",
        entity_id=str(id),
        reason=body.reason,
    )
    session.commit()

    return {"productId": str(id), "aliasSku": alias, "canonicalSku": product.sku}


@router.post("/products/{id}/images", status_code=201)
def add_image(id: uuid_mod.UUID, body: AddImageBody, actor: Actor = Depends(require_permission("product:write"))):
    tenant_id = actor["tenant_id"]
    product_repo.require_product(tenant_id, id)

    if body.isPrimary:
        ProductImage.query.filter_by(product_id=id).update({"is_primary": False})

    session.add(
        ProductImage(
            tenant_id=tenant_id, product_id=id, url=body.url, alt=body.alt, is_primary=body.isPrimary, sort_order=body.sortOrder, bytes=body.bytes, mime=body.mime
        )
    )
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="product.image.added", entity_type="product", entity_id=str(id))
    session.commit()

    return {"data": [product_repo.to_image_api(i) for i in ProductImage.query.filter_by(product_id=id).order_by(ProductImage.sort_order).all()]}


@router.post("/products/{id}/specs", status_code=201)
def add_spec(id: uuid_mod.UUID, body: AddSpecBody, actor: Actor = Depends(require_permission("product:write"))):
    tenant_id = actor["tenant_id"]
    product_repo.require_product(tenant_id, id)

    row = ProductSpec.query.filter_by(product_id=id, key=body.key).first()
    if row:
        row.value = body.value
        row.unit = body.unit
    else:
        session.add(ProductSpec(tenant_id=tenant_id, product_id=id, key=body.key, value=body.value, unit=body.unit, sort_order=body.sortOrder))

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="product.spec.set", entity_type="product", entity_id=str(id))
    session.commit()

    return {"data": [product_repo.to_spec_api(s) for s in ProductSpec.query.filter_by(product_id=id).order_by(ProductSpec.sort_order, ProductSpec.key).all()]}
