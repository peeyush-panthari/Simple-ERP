"""BOM queries + API projections. Ported from
backend_py/app/services/bom_repo.py (full version - supersedes the minimal
`has_approved_bom`-only stub from the products-domain pass)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, or_

from app.core.config import settings
from app.core.db import session
from app.core.errors import not_found, rule_violation
from app.core.money import decimal_str
from app.models.bom import Bom
from app.models.bom_component import BomComponent
from app.models.bom_version import BomVersion
from app.models.product import Product
from app.services.bom_effectivity import EffectivityRange


def find_bom_by_id(tenant_id: uuid.UUID, bom_id: uuid.UUID) -> Bom | None:
    return Bom.query.filter_by(tenant_id=tenant_id, id=bom_id).first()


def require_bom(tenant_id: uuid.UUID, bom_id: uuid.UUID) -> Bom:
    bom = find_bom_by_id(tenant_id, bom_id)
    if not bom:
        raise not_found("Bill of material")
    return bom


def find_bom_by_product(tenant_id: uuid.UUID, product_id: uuid.UUID) -> Bom | None:
    return Bom.query.filter_by(tenant_id=tenant_id, product_id=product_id).first()


def find_version_by_id(tenant_id: uuid.UUID, version_id: uuid.UUID) -> BomVersion | None:
    return BomVersion.query.filter_by(tenant_id=tenant_id, id=version_id).first()


def require_version(tenant_id: uuid.UUID, version_id: uuid.UUID, bom_id: uuid.UUID) -> BomVersion:
    version = find_version_by_id(tenant_id, version_id)
    if not version or version.bom_id != bom_id:
        raise not_found("BOM version")
    return version


def list_versions(tenant_id: uuid.UUID, bom_id: uuid.UUID) -> list[BomVersion]:
    return BomVersion.query.filter_by(tenant_id=tenant_id, bom_id=bom_id).order_by(BomVersion.version.desc()).all()


def components_of(version_id: uuid.UUID) -> list[BomComponent]:
    return BomComponent.query.filter_by(bom_version_id=version_id).order_by(BomComponent.line_no).all()


def find_active_version(tenant_id: uuid.UUID, product_id: uuid.UUID, as_of: date) -> tuple[Bom, BomVersion] | None:
    """Join boms+bom_versions: state='approved', bom active, date range covers
    as_of, tie-break newest version."""
    bom = Bom.query.filter_by(tenant_id=tenant_id, product_id=product_id, status="active").first()
    if not bom:
        return None
    version = (
        BomVersion.query.filter(
            BomVersion.tenant_id == tenant_id,
            BomVersion.bom_id == bom.id,
            BomVersion.state == "approved",
            BomVersion.effective_from <= as_of,
            or_(BomVersion.effective_to.is_(None), BomVersion.effective_to >= as_of),
        )
        .order_by(BomVersion.version.desc())
        .first()
    )
    if not version:
        return None
    return bom, version


def find_active_versions_for_products(tenant_id: uuid.UUID, product_ids: list[uuid.UUID], as_of: date) -> dict[uuid.UUID, tuple[Bom, BomVersion]]:
    """Batched find_active_version(): one query for every product's `boms`
    row plus one for the matching `bom_versions` row."""
    if not product_ids:
        return {}
    boms = Bom.query.filter(Bom.tenant_id == tenant_id, Bom.product_id.in_(product_ids), Bom.status == "active").all()
    bom_by_product_id = {b.product_id: b for b in boms}
    if not bom_by_product_id:
        return {}
    bom_ids = [b.id for b in bom_by_product_id.values()]
    versions = (
        BomVersion.query.filter(
            BomVersion.tenant_id == tenant_id,
            BomVersion.bom_id.in_(bom_ids),
            BomVersion.state == "approved",
            BomVersion.effective_from <= as_of,
            or_(BomVersion.effective_to.is_(None), BomVersion.effective_to >= as_of),
        )
        .order_by(BomVersion.version.desc())
        .all()
    )
    best_version_by_bom_id: dict[uuid.UUID, BomVersion] = {}
    for v in versions:
        best_version_by_bom_id.setdefault(v.bom_id, v)

    result: dict[uuid.UUID, tuple[Bom, BomVersion]] = {}
    for product_id, bom in bom_by_product_id.items():
        version = best_version_by_bom_id.get(bom.id)
        if version:
            result[product_id] = (bom, version)
    return result


def components_of_many(version_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[BomComponent]]:
    """Batched components_of(): one query for every version's components,
    keyed by bom_version_id."""
    if not version_ids:
        return {}
    rows = BomComponent.query.filter(BomComponent.bom_version_id.in_(version_ids)).order_by(BomComponent.bom_version_id, BomComponent.line_no).all()
    by_version: dict[uuid.UUID, list[BomComponent]] = {}
    for row in rows:
        by_version.setdefault(row.bom_version_id, []).append(row)
    return by_version


def approved_ranges(tenant_id: uuid.UUID, bom_id: uuid.UUID) -> list[EffectivityRange]:
    rows = BomVersion.query.filter_by(tenant_id=tenant_id, bom_id=bom_id, state="approved").all()
    return [EffectivityRange(id=str(r.id), version=r.version, from_=r.effective_from, to=r.effective_to) for r in rows]


def lock_bom(tenant_id: uuid.UUID, bom_id: uuid.UUID) -> Bom:
    """SELECT ... FOR UPDATE - must be called inside the caller's transaction."""
    bom = session.query(Bom).filter_by(tenant_id=tenant_id, id=bom_id).with_for_update().first()
    if not bom:
        raise not_found("Bill of material")
    return bom


def next_version_number(bom_id: uuid.UUID) -> int:
    """Caller must have already locked the bom row via lock_bom()."""
    current_max = session.query(func.max(BomVersion.version)).filter(BomVersion.bom_id == bom_id).scalar()
    return (current_max or 0) + 1


def live_component_edges(tenant_id: uuid.UUID, product_id: uuid.UUID) -> list[dict]:
    """Distinct component edges across versions in draft|pending_approval|approved."""
    rows = (
        session.query(BomComponent.component_product_id, BomComponent.component_sku)
        .join(BomVersion, BomVersion.id == BomComponent.bom_version_id)
        .join(Bom, Bom.id == BomVersion.bom_id)
        .filter(
            Bom.tenant_id == tenant_id,
            Bom.product_id == product_id,
            BomVersion.state.in_(["draft", "pending_approval", "approved"]),
        )
        .distinct()
        .all()
    )
    return [{"productId": str(r[0]), "sku": r[1]} for r in rows]


def has_approved_bom(tenant_id: uuid.UUID, product_id: uuid.UUID, as_of: date | None = None) -> bool:
    """Direct-call equivalent of GET /internal/boms/active - for product's publish flow."""
    return find_active_version(tenant_id, product_id, as_of or date.today()) is not None


def explode_for_product(tenant_id: uuid.UUID, product_id: uuid.UUID, quantity, as_of: date, version_id: uuid.UUID | None = None) -> dict:
    """Direct-call equivalent of GET /internal/boms/explode - production's
    posting flow imports this directly (a hard dependency: without the
    recipe, production would consume nothing and inflate finished goods out
    of thin air)."""
    from app.services.bom_explode import explode_bom
    from app.services.bom_tree import TreeContext, build_explode_tree
    from app.services.product_repo import get_summary as get_product_summary

    bom = find_bom_by_product(tenant_id, product_id)
    if not bom:
        raise not_found(f"Bill of material for product {product_id}")

    if version_id:
        version = require_version(tenant_id, version_id, bom.id)
    else:
        active = find_active_version(tenant_id, bom.product_id, as_of)
        version = active[1] if active else None
    if not version:
        raise rule_violation(f"{bom.product_sku} has no approved BOM version effective on {as_of.isoformat()} — approve one before producing against it", code="NO_EFFECTIVE_BOM")

    parent = get_product_summary(tenant_id, bom.product_id)
    ctx = TreeContext(tenant_id=tenant_id, as_of=as_of, max_depth=settings.bom_max_depth)
    tree = build_explode_tree(
        ctx,
        {"product_id": str(bom.product_id), "sku": bom.product_sku, "uom": parent["uom"] if parent else "UNIT", "yield_percent": decimal_str(version.yield_percent)},
        components_of(version.id),
    )
    explosion = explode_bom(tree, quantity, max_depth=settings.bom_max_depth)

    return {
        "bomId": str(bom.id),
        "versionId": str(version.id),
        "version": version.version,
        "asOf": as_of.isoformat(),
        "productId": explosion.product_id,
        "sku": explosion.sku,
        "quantity": explosion.quantity,
        "uom": explosion.uom,
        "requirements": [{"productId": r.product_id, "sku": r.sku, "uom": r.uom, "quantity": r.quantity, "level": r.level} for r in explosion.requirements],
        "subAssemblies": [{"productId": r.product_id, "sku": r.sku, "uom": r.uom, "quantity": r.quantity, "level": r.level} for r in explosion.sub_assemblies],
        "alternates": [{"productId": a.product_id, "sku": a.sku, "uom": a.uom, "quantity": a.quantity, "alternateForLine": a.alternate_for_line, "level": a.level} for a in explosion.alternates],
        "depth": explosion.depth,
    }


# ---- API projections --------------------------------------------------------


def to_bom_api(row: Bom) -> dict:
    return {
        "id": str(row.id),
        "productId": str(row.product_id),
        "productSku": row.product_sku,
        "status": row.status,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def to_version_api(row: BomVersion) -> dict:
    return {
        "id": str(row.id),
        "bomId": str(row.bom_id),
        "version": row.version,
        "state": row.state,
        "yieldPercent": decimal_str(row.yield_percent),
        "effectiveFrom": row.effective_from.isoformat() if row.effective_from else None,
        "effectiveTo": row.effective_to.isoformat() if row.effective_to else None,
        "notes": row.notes,
        "routingNotes": row.routing_notes,
        "approvedBy": str(row.approved_by) if row.approved_by else None,
        "approvedAt": row.approved_at.isoformat() if row.approved_at else None,
        "rejectedReason": row.rejected_reason,
        "costRollup": decimal_str(row.cost_rollup) if row.cost_rollup is not None else None,
        "currency": row.currency,
        "revisedFromId": str(row.revised_from_id) if row.revised_from_id else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def to_component_api(row: BomComponent, product_name: str | None = None) -> dict:
    return {
        "id": str(row.id),
        "lineNo": row.line_no,
        "productId": str(row.component_product_id),
        "sku": row.component_sku,
        "productName": product_name,
        "quantity": decimal_str(row.quantity),
        "uom": row.uom,
        "scrapPercent": decimal_str(row.scrap_percent),
        "isAlternate": row.is_alternate,
        "alternateForLine": row.alternate_for_line,
        "notes": row.notes,
    }


def components_api_of(tenant_id: uuid.UUID, version_id: uuid.UUID) -> list[dict]:
    components = components_of(version_id)
    product_ids = {c.component_product_id for c in components}
    names_by_id = (
        {p.id: p.name for p in Product.query.filter(Product.tenant_id == tenant_id, Product.id.in_(product_ids)).all()}
        if product_ids
        else {}
    )
    return [to_component_api(c, product_name=names_by_id.get(c.component_product_id)) for c in components]


def components_api_of_many(tenant_id: uuid.UUID, version_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    components_by_version = components_of_many(version_ids)
    all_product_ids = {c.component_product_id for components in components_by_version.values() for c in components}
    names_by_id = (
        {p.id: p.name for p in Product.query.filter(Product.tenant_id == tenant_id, Product.id.in_(all_product_ids)).all()}
        if all_product_ids
        else {}
    )
    return {
        version_id: [to_component_api(c, product_name=names_by_id.get(c.component_product_id)) for c in components]
        for version_id, components in components_by_version.items()
    }
