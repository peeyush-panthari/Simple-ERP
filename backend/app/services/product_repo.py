"""Product queries + API projections. Ported from backend_py/app/services/product_repo.py.

`load_categories` is memoised for the life of a request, as in the original (a page with many
BOM/GRN/PO lines calls `_summarise()` once per line and would otherwise re-scan
`product_categories` per line). Flask kept it on `g`; here it is keyed by the request-scope token
that also scopes the DB session, and dropped when the request ends (`on_request_end`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func

from app.core.db import current_request_scope, on_request_end, session
from app.core.errors import not_found
from app.core.money import decimal_str
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.models.product_category import ProductCategory
from app.models.product_image import ProductImage
from app.models.product_spec import ProductSpec
from app.models.uom_conversion import UomConversion
from app.services.product_category import CategoryNode


def find_product(tenant_id: uuid.UUID, product_id: uuid.UUID) -> Product | None:
    return Product.query.filter_by(tenant_id=tenant_id, id=product_id).first()


def require_product(tenant_id: uuid.UUID, product_id: uuid.UUID) -> Product:
    product = find_product(tenant_id, product_id)
    if not product:
        raise not_found("Product")
    return product


def find_by_sku(tenant_id: uuid.UUID, sku: str) -> Product | None:
    """Resolves a SKU through aliases, so retired paperwork still finds the row."""
    direct = Product.query.filter(Product.tenant_id == tenant_id, func.upper(Product.sku) == sku.upper()).first()
    if direct:
        return direct
    alias = ProductAlias.query.filter(ProductAlias.tenant_id == tenant_id, func.upper(ProductAlias.alias_sku) == sku.upper()).first()
    if alias:
        return Product.query.filter_by(tenant_id=tenant_id, id=alias.product_id).first()
    return None


def find_by_skus(tenant_id: uuid.UUID, skus: list[str]) -> dict[str, Product]:
    """Batched find_by_sku, for CSV bulk uploads - keyed by the UPPERCASED sku."""
    wanted = {sku.upper() for sku in skus if sku}
    if not wanted:
        return {}

    resolved: dict[str, Product] = {}
    for product in Product.query.filter(Product.tenant_id == tenant_id, func.upper(Product.sku).in_(wanted)).all():
        resolved[product.sku.upper()] = product

    unresolved = wanted - resolved.keys()
    if not unresolved:
        return resolved

    aliases = ProductAlias.query.filter(
        ProductAlias.tenant_id == tenant_id, func.upper(ProductAlias.alias_sku).in_(unresolved)
    ).all()
    if not aliases:
        return resolved

    by_id = {
        p.id: p
        for p in Product.query.filter(
            Product.tenant_id == tenant_id, Product.id.in_({a.product_id for a in aliases})
        ).all()
    }
    for alias in aliases:
        target = by_id.get(alias.product_id)
        if target is not None:
            resolved.setdefault(alias.alias_sku.upper(), target)
    return resolved


def find_by_name_and_make(tenant_id: uuid.UUID, name: str, make: str, exclude_id: uuid.UUID | None = None) -> Product | None:
    q = Product.query.filter(
        Product.tenant_id == tenant_id,
        func.lower(Product.name) == name.strip().lower(),
        func.lower(Product.make) == make.strip().lower(),
    )
    if exclude_id:
        q = q.filter(Product.id != exclude_id)
    return q.first()


_category_cache: dict[str, dict[str, dict[str, CategoryNode]]] = {}  # request-scope token -> tenant -> nodes
on_request_end(lambda token: _category_cache.pop(token, None))


def load_categories(tenant_id: uuid.UUID) -> dict[str, CategoryNode]:
    """Category tree for a tenant, memoised for the life of the request.

    Callers may reshape the mapping they get back (patch_category simulates a reparent in it), so
    each call gets its own dict; the CategoryNode values are read-only and shared.
    """
    token = current_request_scope()
    if token is None:
        rows = ProductCategory.query.filter_by(tenant_id=tenant_id).all()
        return {str(r.id): to_category_node(r) for r in rows}

    cache = _category_cache.setdefault(token, {})
    key = str(tenant_id)
    nodes = cache.get(key)
    if nodes is None:
        rows = ProductCategory.query.filter_by(tenant_id=tenant_id).all()
        nodes = {str(r.id): to_category_node(r) for r in rows}
        cache[key] = nodes
    return dict(nodes)


def invalidate_category_cache() -> None:
    """Drops the request-scoped cache after a category write, so a read later in the same request sees the new tree."""
    token = current_request_scope()
    if token is not None:
        _category_cache.pop(token, None)


def to_category_node(row: ProductCategory) -> CategoryNode:
    return CategoryNode(
        id=str(row.id),
        code=row.code,
        product_category=row.product_category,
        parent_id=str(row.parent_id) if row.parent_id else None,
        product_types=row.product_types or [],
        requires_batch=row.requires_batch,
        requires_expiry=row.requires_expiry,
        default_tax_code=row.default_tax_code,
        status=row.status,
    )


def load_conversions(product_id: uuid.UUID) -> list[dict]:
    rows = UomConversion.query.filter_by(product_id=product_id).all()
    return [{"fromUom": r.from_uom, "toUom": r.to_uom, "factor": decimal_str(r.factor)} for r in rows]


def count_images(product_id: uuid.UUID) -> int:
    return ProductImage.query.filter_by(product_id=product_id).count()


def count_specs(product_id: uuid.UUID) -> int:
    return ProductSpec.query.filter_by(product_id=product_id).count()


# ---- API projections --------------------------------------------------------


def to_product_api(row: Product) -> dict:
    return {
        "id": str(row.id),
        "sku": row.sku,
        "name": row.name,
        "make": row.make,
        "modelNumber": row.model_number,
        "description": row.description,
        "type": row.type,
        "categoryId": str(row.category_id) if row.category_id else None,
        "uom": row.uom,
        "alternateUoms": row.alternate_uoms or [],
        "hsnCode": row.hsn_code,
        "status": row.status,
        "batchTracked": row.batch_tracked,
        "expiryTracked": row.expiry_tracked,
        "storageConditions": row.storage_conditions,
        "reorderPoint": decimal_str(row.reorder_point) if row.reorder_point is not None else None,
        "reorderQty": decimal_str(row.reorder_qty) if row.reorder_qty is not None else None,
        "leadTimeDays": row.lead_time_days,
        "currency": row.currency,
        "purchasable": row.purchasable,
        "sellable": row.sellable,
        "weightKg": decimal_str(row.weight_kg) if row.weight_kg is not None else None,
        "volumeM3": decimal_str(row.volume_m3) if row.volume_m3 is not None else None,
        "publishedAt": row.published_at.isoformat() if row.published_at else None,
        "deprecatedAt": row.deprecated_at.isoformat() if row.deprecated_at else None,
        "deprecatedReason": row.deprecated_reason,
        "firstTransactionAt": row.first_transaction_at.isoformat() if row.first_transaction_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def to_category_api(row: ProductCategory) -> dict:
    return {
        "id": str(row.id),
        "code": row.code,
        "productCategory": row.product_category,
        "parentId": str(row.parent_id) if row.parent_id else None,
        "productTypes": row.product_types or [],
        "requiresBatch": row.requires_batch,
        "requiresExpiry": row.requires_expiry,
        "defaultTaxCode": row.default_tax_code,
        "status": row.status,
    }


def to_image_api(row: ProductImage) -> dict:
    return {"id": str(row.id), "url": row.url, "alt": row.alt, "isPrimary": row.is_primary, "sortOrder": row.sort_order, "bytes": row.bytes, "mime": row.mime}


def to_spec_api(row: ProductSpec) -> dict:
    return {"id": str(row.id), "key": row.key, "value": row.value, "unit": row.unit, "sortOrder": row.sort_order}


# ---- direct-call helpers other domains import instead of an HTTP hop -------


def _summarise(product: Product, tenant_id: uuid.UUID) -> dict:
    categories = load_categories(tenant_id)
    category = categories.get(str(product.category_id)) if product.category_id else None
    return {
        "id": str(product.id),
        "sku": product.sku,
        "name": product.name,
        "make": product.make,
        "type": product.type,
        "uom": product.uom,
        "alternateUoms": product.alternate_uoms or [],
        "hsnCode": product.hsn_code,
        "status": product.status,
        "purchasable": product.status == "active" and product.purchasable,
        "sellable": product.status == "active" and product.sellable,
        "batchTracked": product.batch_tracked,
        "expiryTracked": product.expiry_tracked,
        "categoryId": str(product.category_id) if product.category_id else None,
        "categoryName": category.product_category if category else None,
        "currency": product.currency,
    }


def summarise(product: Product, tenant_id: uuid.UUID) -> dict:
    return _summarise(product, tenant_id)


def get_summary(tenant_id: uuid.UUID, product_id: uuid.UUID) -> dict | None:
    product = find_product(tenant_id, product_id)
    return _summarise(product, tenant_id) if product else None


def get_summary_by_sku(tenant_id: uuid.UUID, sku: str) -> dict | None:
    product = find_by_sku(tenant_id, sku)
    return _summarise(product, tenant_id) if product else None


def get_summaries(tenant_id: uuid.UUID, product_ids: list[uuid.UUID]) -> dict[str, dict]:
    """Batched get_summary - one query for however many distinct products a
    page needs, not one per row."""
    if not product_ids:
        return {}
    products = Product.query.filter(Product.tenant_id == tenant_id, Product.id.in_(product_ids)).all()
    return {str(p.id): _summarise(p, tenant_id) for p in products}


def mark_transacted(tenant_id: uuid.UUID, product_id: uuid.UUID, reference: str) -> dict | None:
    """First caller wins - freezes SKU/UOM immutability going forward. Idempotent."""
    product = find_product(tenant_id, product_id)
    if not product:
        return None
    if product.first_transaction_at is None:
        product.first_transaction_at = datetime.now(timezone.utc)
        product.first_transaction_ref = reference
    return {"productId": str(product_id), "firstTransactionAt": product.first_transaction_at.isoformat(), "firstTransactionRef": product.first_transaction_ref}
