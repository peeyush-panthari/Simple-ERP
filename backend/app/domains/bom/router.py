"""Bills of material: create/version/submit/approve/reject/revise, cost
rollup, explode. Ported 1:1 (behavior) from backend_py/app/routes/boms.py."""

from __future__ import annotations

import csv
import io
import uuid as uuid_mod
from dataclasses import dataclass
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, or_

from app.core.auth import Actor, require_any_permission, require_permission
from app.core.audit import audit
from app.core.config import settings
from app.core.db import session
from app.core.errors import ProblemError, conflict, not_found, rule_violation
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.money import decimal_str
from app.core.pagination import ListQuery, list_response, offset_of
from app.domains.bom.schemas import (
    ApproveBody,
    BomBulkUploadBody,
    ComponentBody,
    CreateBomBody,
    PatchVersionBody,
    RejectBody,
    ReviseBody,
    VersionBody,
)
from app.models.bom import Bom
from app.models.bom_approval import BomApproval
from app.models.bom_component import BomComponent
from app.models.bom_version import BomVersion
from app.services import bom_repo, product_repo
from app.services.bom_components import ComponentInput, validate_component_structure
from app.services.bom_cost import rollup_cost
from app.services.bom_cycle import BomNode, find_cycle_for_proposed_components, format_path
from app.services.bom_effectivity import describe_range, find_overlaps, plan_retirement
from app.services.bom_state import explain_transition, is_editable
from app.services.bom_tree import TreeContext, build_cost_tree
from app.services.uom import can_convert

router = APIRouter(prefix="/api/v1", tags=["bom"])


@dataclass
class NumberedComponent:
    line_no: int
    component_product_id: str
    component_sku: str
    quantity: str
    uom: str
    scrap_percent: str
    is_alternate: bool
    alternate_for_line: int | None
    notes: str | None


def _assert_parent_eligible(parent: dict | None, product_id) -> None:
    if not parent:
        raise not_found("Product")
    if parent["type"] != "finished_good":
        raise rule_violation(
            f"Only finished goods can own a bill of material — {parent['sku']} is a {parent['type'].replace('_', ' ')}",
            code="BOM_PARENT_NOT_FINISHED_GOOD",
        )


def _validate_components(tenant_id, input_components: list[ComponentBody], parent: dict) -> list[NumberedComponent]:
    """Structural checks, then component eligibility against the Product
    master, then the cycle walk."""
    numbered = [
        NumberedComponent(
            line_no=c.lineNo or (i + 1),
            component_product_id=str(c.componentProductId),
            component_sku="",
            quantity=c.quantity,
            uom=c.uom,
            scrap_percent=c.scrapPercent,
            is_alternate=c.isAlternate,
            alternate_for_line=c.alternateForLine,
            notes=c.notes,
        )
        for i, c in enumerate(input_components)
    ]

    structural = [
        ComponentInput(
            line_no=c.line_no,
            component_product_id=c.component_product_id,
            component_sku=c.component_sku,
            quantity=c.quantity,
            uom=c.uom,
            scrap_percent=c.scrap_percent,
            is_alternate=c.is_alternate,
            alternate_for_line=c.alternate_for_line,
        )
        for c in numbered
    ]
    errors: list[dict] = list(validate_component_structure(structural))

    component_summaries = product_repo.get_summaries(tenant_id, [uuid_mod.UUID(l.component_product_id) for l in numbered])

    for i, line in enumerate(numbered):
        product = component_summaries.get(line.component_product_id)
        field = f"components.{i}"
        if not product:
            errors.append({"field": field, "message": f"Product {line.component_product_id} does not exist"})
            continue
        line.component_sku = product["sku"]

        if product["id"] == parent["productId"]:
            errors.append({"field": field, "message": f"{product['sku']} cannot be a component of itself"})
        if product["status"] != "active":
            errors.append({"field": field, "message": f"{product['sku']} is {product['status']} — only published products can be BOM components"})
        allowed = ["raw_material", "consumable", "finished_good"] if settings.allow_nested_bom else ["raw_material", "consumable"]
        if product["type"] not in allowed:
            if settings.allow_nested_bom:
                errors.append({"field": field, "message": f"{product['sku']} is a {product['type'].replace('_', ' ')} and cannot be a component"})
            else:
                errors.append(
                    {"field": field, "message": f"{product['sku']} is a {product['type'].replace('_', ' ')} — nested BOMs are disabled, so only raw materials and consumables may be components"}
                )
        if line.uom != product["uom"] and not can_convert(line.uom, product["uom"]):
            errors.append({"field": f"{field}.uom", "message": f"{line.uom} cannot be converted to {product['sku']}'s base unit {product['uom']}"})

    if errors:
        joined = "; ".join(e["message"] for e in errors)
        raise rule_violation(
            f"{parent['sku']}'s component list has {len(errors)} problem{'s' if len(errors) > 1 else ''}: {joined}",
            code="BOM_COMPONENTS_INVALID",
            meta={"errors": errors},
        )

    def resolve(node: BomNode) -> list[BomNode]:
        return [BomNode(product_id=e["productId"], sku=e["sku"]) for e in bom_repo.live_component_edges(tenant_id, uuid_mod.UUID(node.product_id))]

    proposed = [BomNode(product_id=c.component_product_id, sku=c.component_sku) for c in numbered]
    finding = find_cycle_for_proposed_components(
        BomNode(product_id=str(parent["productId"]), sku=parent["sku"]), proposed, resolve, max_depth=settings.bom_max_depth
    )
    if finding and finding.kind == "cycle":
        raise rule_violation(f"This would create a circular bill of material: {format_path(finding.path)}", code="BOM_CIRCULAR_REFERENCE", meta={"path": [n.sku for n in finding.path]})
    if finding and finding.kind == "depth-exceeded":
        raise rule_violation(f"BOM nesting exceeds {finding.max_depth} levels ({format_path(finding.path)}) — flatten the structure", code="BOM_TOO_DEEP")

    return numbered


def _insert_components(tenant_id, version_id, components: list[NumberedComponent]) -> None:
    for c in components:
        session.add(
            BomComponent(
                tenant_id=tenant_id,
                bom_version_id=version_id,
                line_no=c.line_no,
                component_product_id=c.component_product_id,
                component_sku=c.component_sku,
                quantity=c.quantity,
                uom=c.uom,
                scrap_percent=c.scrap_percent,
                is_alternate=c.is_alternate,
                alternate_for_line=c.alternate_for_line,
                notes=c.notes,
            )
        )


def _assert_transition(from_state: str, to_state: str) -> None:
    problem = explain_transition(from_state, to_state)
    if problem:
        raise rule_violation(problem["detail"], code=problem["code"])


#  Production posting depends on looking up a product's BOM and exploding it -
#  reachable only via inventory:produce/inventory:read today, not bom:read.
_BOM_LOOKUP_PERMISSIONS = ("bom:read", "inventory:read")


@router.get("/boms")
def list_boms(actor: Actor = Depends(require_any_permission(*_BOM_LOOKUP_PERMISSIONS)), query: ListQuery = Depends(), productId: uuid_mod.UUID | None = None):
    tenant_id = actor["tenant_id"]

    q = Bom.query.filter(Bom.tenant_id == tenant_id)
    if productId:
        q = q.filter(Bom.product_id == productId)
    if query.q:
        q = q.filter(Bom.product_sku.ilike(f"%{query.q}%"))

    total = q.count()
    rows = q.order_by(Bom.product_sku).limit(query.limit).offset(offset_of(query)).all()

    bom_ids = [r.id for r in rows]
    version_counts: dict = {}
    active_by_bom: dict = {}
    latest_by_bom: dict = {}
    if bom_ids:
        today = date.today()
        version_counts = dict(
            session.query(BomVersion.bom_id, func.count())
            .filter(BomVersion.bom_id.in_(bom_ids))
            .group_by(BomVersion.bom_id)
            .all()
        )
        for bom_id, version in (
            session.query(BomVersion.bom_id, BomVersion.version)
            .filter(
                BomVersion.bom_id.in_(bom_ids),
                BomVersion.state == "approved",
                BomVersion.effective_from <= today,
                or_(BomVersion.effective_to.is_(None), BomVersion.effective_to >= today),
            )
            .order_by(BomVersion.version.asc())
            .all()
        ):
            active_by_bom[bom_id] = version
        for bom_id, state in (
            session.query(BomVersion.bom_id, BomVersion.state)
            .filter(BomVersion.bom_id.in_(bom_ids))
            .order_by(BomVersion.version.asc())
            .all()
        ):
            latest_by_bom[bom_id] = state

    summaries = product_repo.get_summaries(tenant_id, [r.product_id for r in rows])

    data = []
    for r in rows:
        version_count = version_counts.get(r.id, 0)
        active_version = active_by_bom.get(r.id)
        latest_state = latest_by_bom.get(r.id)
        summary = summaries.get(str(r.product_id))
        data.append(
            {
                "id": str(r.id),
                "productId": str(r.product_id),
                "productSku": r.product_sku,
                "productName": summary["name"] if summary else None,
                "productCategory": summary["categoryName"] if summary else None,
                "status": r.status,
                "versionCount": version_count,
                "activeVersion": active_version,
                "latestState": latest_state,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
        )

    return list_response(data, query, total)


@router.get("/boms/{id}")
def get_bom(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("bom:read"))):
    tenant_id = actor["tenant_id"]
    bom = bom_repo.require_bom(tenant_id, id)
    versions = bom_repo.list_versions(tenant_id, id)
    active = bom_repo.find_active_version(tenant_id, bom.product_id, date.today())

    components_by_version = bom_repo.components_api_of_many(tenant_id, [v.id for v in versions])

    result = bom_repo.to_bom_api(bom)
    result["activeVersionId"] = str(active[1].id) if active else None
    result["versions"] = [{**bom_repo.to_version_api(v), "components": components_by_version.get(v.id, [])} for v in versions]
    return result


@router.get("/boms/{id}/versions")
def list_bom_versions(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("bom:read"))):
    tenant_id = actor["tenant_id"]
    bom_repo.require_bom(tenant_id, id)
    versions = bom_repo.list_versions(tenant_id, id)
    return {"data": [bom_repo.to_version_api(v) for v in versions]}


def _create_bom(tenant_id, actor: Actor, body: CreateBomBody) -> Bom:
    """Shared by the single-BOM create route and the bulk-upload route."""
    parent_summary = product_repo.get_summary(tenant_id, body.productId)
    _assert_parent_eligible(parent_summary, body.productId)
    parent = {"productId": str(body.productId), "sku": parent_summary["sku"]}

    existing = bom_repo.find_bom_by_product(tenant_id, body.productId)
    if existing:
        raise conflict(f"{parent['sku']} already has a bill of material — add a version to it instead (POST /boms/{existing.id}/versions)", code="BOM_EXISTS")

    components = _validate_components(tenant_id, body.components, parent)

    bom = Bom(tenant_id=tenant_id, product_id=body.productId, product_sku=parent["sku"], created_by=actor["user_id"])
    session.add(bom)
    session.flush()

    version = BomVersion(
        tenant_id=tenant_id,
        bom_id=bom.id,
        version=1,
        state="draft",
        yield_percent=body.yieldPercent,
        effective_from=body.effectiveFrom,
        effective_to=body.effectiveTo,
        notes=body.notes,
        routing_notes=body.routingNotes,
        currency=settings.base_currency,
        created_by=actor["user_id"],
    )
    session.add(version)
    session.flush()
    _insert_components(tenant_id, version.id, components)

    version.state = "approved"
    version.approved_by = actor["user_id"]
    version.approved_at = datetime.now(timezone.utc)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="bom.created", entity_type="bom", entity_id=str(bom.id))
    session.commit()
    return bom


@router.post("/boms", status_code=201)
def create_bom(body: CreateBomBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("bom:write"))):
    """Creating a BOM and its first version is one call. Approval flow
    removed: the first version is approved (effective) on creation."""
    tenant_id = actor["tenant_id"]

    def _do():
        bom = _create_bom(tenant_id, actor, body)
        version = bom_repo.list_versions(tenant_id, bom.id)[0]
        return 201, {**bom_repo.to_bom_api(bom), "version": bom_repo.to_version_api(version)}

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


BULK_UPLOAD_REQUIRED_COLUMNS = ["productSku", "effectiveFrom", "componentSku", "quantity", "uom"]


def _parse_bool(value: str, default: bool) -> bool:
    v = (value or "").strip().lower()
    if v in ("true", "1", "yes", "y"):
        return True
    if v in ("false", "0", "no", "n"):
        return False
    return default


@router.post("/boms/bulk-upload")
def bulk_upload_boms(body: BomBulkUploadBody, actor: Actor = Depends(require_permission("bom:write"))):
    """Creates many BOMs (each for a different finished good) from one CSV
    in a single request - one row per component, grouped by productSku."""
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for row_number, raw_row in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k}
        row["_rowNumber"] = row_number
        sku = row.get("productSku") or ""
        if not sku:
            continue
        if sku not in groups:
            groups[sku] = []
            order.append(sku)
        groups[sku].append(row)

    all_skus = list(order) + [r.get("componentSku") or "" for sku in order for r in groups[sku]]
    products_by_sku = product_repo.find_by_skus(tenant_id, all_skus)

    results = []
    for product_sku in order:
        rows = groups[product_sku]
        first = rows[0]
        errors: list[str] = []

        parent_row = products_by_sku.get(product_sku.upper())
        parent = product_repo.summarise(parent_row, tenant_id) if parent_row else None
        product_name = parent["name"] if parent else None
        if not parent:
            errors.append(f"Product SKU '{product_sku}' not found")
        elif parent["type"] != "finished_good":
            errors.append(f"{product_sku} is a {parent['type'].replace('_', ' ')} — only finished goods can own a bill of material")

        effective_from_raw = first.get("effectiveFrom") or ""
        effective_from = None
        try:
            effective_from = date.fromisoformat(effective_from_raw)
        except ValueError:
            errors.append(f"Invalid effectiveFrom '{effective_from_raw}' — use YYYY-MM-DD")

        effective_to = None
        if first.get("effectiveTo"):
            try:
                effective_to = date.fromisoformat(first["effectiveTo"])
            except ValueError:
                errors.append(f"Invalid effectiveTo '{first['effectiveTo']}' — use YYYY-MM-DD")

        components: list[ComponentBody] = []
        for r in rows:
            row_no = r["_rowNumber"]
            component_sku = r.get("componentSku") or ""
            if not component_sku:
                errors.append(f"Row {row_no}: componentSku is required")
                continue
            component_product = products_by_sku.get(component_sku.upper())
            if not component_product:
                errors.append(f"Row {row_no}: component SKU '{component_sku}' not found")
                continue
            quantity_raw = r.get("quantity") or ""
            if not quantity_raw:
                errors.append(f"Row {row_no}: quantity is required")
                continue
            uom = r.get("uom") or ""
            if not uom:
                errors.append(f"Row {row_no}: uom is required")
                continue
            try:
                components.append(
                    ComponentBody(
                        componentProductId=component_product.id,
                        quantity=quantity_raw,
                        uom=uom,
                        scrapPercent=r.get("scrapPercent") or "0",
                        isAlternate=_parse_bool(r.get("isAlternate", ""), False),
                        alternateForLine=int(r["alternateForLine"]) if r.get("alternateForLine") else None,
                        notes=r.get("componentNotes") or None,
                    )
                )
            except (ValidationError, ValueError) as exc:
                message = exc.errors()[0].get("msg", "invalid component data") if isinstance(exc, ValidationError) else str(exc)
                errors.append(f"Row {row_no}: {message}")

        if not errors and not components:
            errors.append("No components")

        if errors:
            results.append({"productSku": product_sku, "productName": product_name, "status": "error", "error": "; ".join(errors), "rows": rows})
            continue

        try:
            create_body = CreateBomBody(
                productId=parent["id"],
                yieldPercent=first.get("yieldPercent") or "100",
                effectiveFrom=effective_from,
                effectiveTo=effective_to,
                notes=first.get("notes") or None,
                routingNotes=first.get("routingNotes") or None,
                components=components,
            )
        except ValidationError as exc:
            results.append({"productSku": product_sku, "productName": product_name, "status": "error", "error": exc.errors()[0].get("msg", "invalid BOM data"), "rows": rows})
            continue

        try:
            bom = _create_bom(tenant_id, actor, create_body)
            results.append({"productSku": product_sku, "productName": product_name, "status": "success", "bomId": str(bom.id), "rows": rows})
        except ProblemError as exc:
            session.rollback()
            results.append({"productSku": product_sku, "productName": product_name, "status": "error", "error": exc.detail, "rows": rows})
        except Exception as exc:  # noqa: BLE001 - one bad group must not fail the whole batch
            session.rollback()
            results.append({"productSku": product_sku, "productName": product_name, "status": "error", "error": str(exc), "rows": rows})

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    return {
        "summary": {"totalGroups": len(results), "successCount": success_count, "errorCount": error_count},
        "results": [
            {
                "productSku": r["productSku"],
                "productName": r.get("productName"),
                "status": r["status"],
                "bomId": r.get("bomId"),
                "error": r.get("error"),
                "rows": [{k: v for k, v in row.items() if k != "_rowNumber"} for row in r["rows"]] if r["status"] == "error" else [],
            }
            for r in results
        ],
    }


@router.post("/boms/{id}/versions", status_code=201)
def add_version(id: uuid_mod.UUID, body: VersionBody, actor: Actor = Depends(require_permission("bom:write"))):
    """Approval flow removed: a new version supersedes the current one and
    is approved (effective) immediately."""
    tenant_id = actor["tenant_id"]
    bom = bom_repo.require_bom(tenant_id, id)
    parent = {"productId": str(bom.product_id), "sku": bom.product_sku}
    components = _validate_components(tenant_id, body.components, parent)

    bom_repo.lock_bom(tenant_id, id)
    version_no = bom_repo.next_version_number(id)

    version = BomVersion(
        tenant_id=tenant_id,
        bom_id=id,
        version=version_no,
        state="draft",
        yield_percent=body.yieldPercent,
        effective_from=body.effectiveFrom,
        effective_to=body.effectiveTo,
        notes=body.notes,
        routing_notes=body.routingNotes,
        currency=settings.base_currency,
        created_by=actor["user_id"],
    )
    session.add(version)
    session.flush()
    _insert_components(tenant_id, version.id, components)

    BomVersion.query.filter_by(bom_id=id, state="approved").update({"state": "retired"})
    version.state = "approved"
    version.approved_by = actor["user_id"]
    version.approved_at = datetime.now(timezone.utc)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="bom.version.created", entity_type="bom", entity_id=str(id))
    session.commit()

    return {**bom_repo.to_version_api(version), "components": bom_repo.components_api_of(tenant_id, version.id)}


@router.patch("/boms/{id}/versions/{versionId}")
def patch_version(id: uuid_mod.UUID, versionId: uuid_mod.UUID, body: PatchVersionBody, actor: Actor = Depends(require_permission("bom:write"))):
    tenant_id = actor["tenant_id"]
    bom = bom_repo.require_bom(tenant_id, id)
    version = bom_repo.require_version(tenant_id, versionId, id)

    if not is_editable(version.state):
        problem = explain_transition(version.state, "draft") or {"code": "BOM_VERSION_IMMUTABLE", "detail": "This version can no longer be edited."}
        raise rule_violation(problem["detail"], code=problem["code"])

    parent = {"productId": str(bom.product_id), "sku": bom.product_sku}
    components = _validate_components(tenant_id, body.components, parent) if body.components is not None else None

    if body.yieldPercent is not None:
        version.yield_percent = body.yieldPercent
    if body.effectiveFrom is not None:
        version.effective_from = body.effectiveFrom
    if "effectiveTo" in body.model_fields_set:
        version.effective_to = body.effectiveTo
    if "notes" in body.model_fields_set:
        version.notes = body.notes
    if "routingNotes" in body.model_fields_set:
        version.routing_notes = body.routingNotes

    if components is not None:
        BomComponent.query.filter_by(bom_version_id=versionId).delete()
        _insert_components(tenant_id, versionId, components)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="bom.version.updated", entity_type="bom", entity_id=str(id))
    session.commit()

    return {**bom_repo.to_version_api(version), "components": bom_repo.components_api_of(tenant_id, versionId)}


@router.post("/boms/{id}/versions/{versionId}/submit")
def submit_version(id: uuid_mod.UUID, versionId: uuid_mod.UUID, actor: Actor = Depends(require_permission("bom:write"))):
    tenant_id = actor["tenant_id"]
    version = bom_repo.require_version(tenant_id, versionId, id)
    _assert_transition(version.state, "pending_approval")

    version.state = "pending_approval"
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="bom.version.submitted", entity_type="bom", entity_id=str(id))
    session.commit()

    return bom_repo.to_version_api(version)


@router.post("/boms/{id}/versions/{versionId}/approve")
def approve_version(id: uuid_mod.UUID, versionId: uuid_mod.UUID, body: ApproveBody, actor: Actor = Depends(require_permission("bom:approve"))):
    """The expensive step: re-validates the whole structure, checks
    effective-date overlap against every other approved version, computes
    the cost rollup, and retires predecessors - all in one transaction."""
    tenant_id = actor["tenant_id"]
    bom = bom_repo.require_bom(tenant_id, id)
    version = bom_repo.require_version(tenant_id, versionId, id)
    _assert_transition(version.state, "approved")

    if version.created_by == actor["user_id"] and not actor.get("internal"):
        raise rule_violation("A BOM version must be approved by someone other than its author", code="SELF_APPROVAL_BLOCKED")

    components = bom_repo.components_of(versionId)
    component_bodies = [
        ComponentBody(
            lineNo=c.line_no,
            componentProductId=c.component_product_id,
            quantity=decimal_str(c.quantity),
            uom=c.uom,
            scrapPercent=decimal_str(c.scrap_percent),
            isAlternate=c.is_alternate,
            alternateForLine=c.alternate_for_line,
            notes=c.notes,
        )
        for c in components
    ]
    _validate_components(tenant_id, component_bodies, {"productId": str(bom.product_id), "sku": bom.product_sku})

    incoming_from, incoming_to = version.effective_from, version.effective_to
    ranges = [r for r in bom_repo.approved_ranges(tenant_id, id) if r.id != str(versionId)]
    plan = plan_retirement(incoming_from, incoming_to, ranges)
    handled = {r.id for r in plan.retire} | {t[0].id for t in plan.truncate}
    unresolved = find_overlaps(incoming_from, incoming_to, [r for r in ranges if r.id not in handled])
    if unresolved:
        overlaps_str = ", ".join(f"v{r.version} ({describe_range(r.from_, r.to)})" for r in unresolved)
        raise rule_violation(
            f"Effective range {describe_range(incoming_from, incoming_to)} overlaps approved version {overlaps_str} — only one approved version may be effective at a time",
            code="BOM_EFFECTIVITY_OVERLAP",
            meta={"overlaps": [{"id": r.id, "version": r.version} for r in unresolved]},
        )

    ctx = TreeContext(tenant_id=tenant_id, as_of=date.today(), max_depth=settings.bom_max_depth)
    tree = build_cost_tree(ctx, bom.product_sku, decimal_str(version.yield_percent), components)
    rollup = rollup_cost(tree)

    for r in plan.retire:
        BomVersion.query.filter_by(id=r.id).update({"state": "retired"})
    for r, new_to in plan.truncate:
        BomVersion.query.filter_by(id=r.id).update({"effective_to": new_to})

    version.state = "approved"
    version.approved_by = actor["user_id"]
    version.approved_at = datetime.now(timezone.utc)
    version.cost_rollup = rollup.unit_cost
    version.currency = settings.base_currency

    session.add(BomApproval(tenant_id=tenant_id, version_id=versionId, actor=actor["user_id"], decision="approved", reason=body.reason))
    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="bom.version.approved",
        entity_type="bom",
        entity_id=str(id),
        reason=body.reason,
        meta={"unitCost": rollup.unit_cost, "unpricedSkus": rollup.unpriced_skus},
    )
    session.commit()

    return {
        **bom_repo.to_version_api(version),
        "costRollup": {"unitCost": rollup.unit_cost, "unpricedSkus": rollup.unpriced_skus},
        "retiredVersions": [r.version for r in plan.retire],
        "truncatedVersions": [{"version": r.version, "effectiveTo": new_to.isoformat()} for r, new_to in plan.truncate],
    }


@router.post("/boms/{id}/versions/{versionId}/reject")
def reject_version(id: uuid_mod.UUID, versionId: uuid_mod.UUID, body: RejectBody, actor: Actor = Depends(require_permission("bom:approve"))):
    tenant_id = actor["tenant_id"]
    version = bom_repo.require_version(tenant_id, versionId, id)
    _assert_transition(version.state, "rejected")

    version.state = "rejected"
    version.rejected_reason = body.reason
    session.add(BomApproval(tenant_id=tenant_id, version_id=versionId, actor=actor["user_id"], decision="rejected", reason=body.reason))
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="bom.version.rejected", entity_type="bom", entity_id=str(id), reason=body.reason)
    session.commit()

    return bom_repo.to_version_api(version)


@router.post("/boms/{id}/versions/{versionId}/revise", status_code=201)
def revise_version(id: uuid_mod.UUID, versionId: uuid_mod.UUID, body: ReviseBody, actor: Actor = Depends(require_permission("bom:write"))):
    """Clone any version into a fresh draft - the only way to change an approved BOM."""
    tenant_id = actor["tenant_id"]
    bom_repo.require_bom(tenant_id, id)
    source = bom_repo.require_version(tenant_id, versionId, id)
    components = bom_repo.components_of(versionId)

    bom_repo.lock_bom(tenant_id, id)
    version_no = bom_repo.next_version_number(id)

    new_version = BomVersion(
        tenant_id=tenant_id,
        bom_id=id,
        version=version_no,
        state="draft",
        yield_percent=source.yield_percent,
        effective_from=body.effectiveFrom,
        effective_to=None,
        notes=body.notes or source.notes,
        routing_notes=source.routing_notes,
        currency=source.currency,
        revised_from_id=versionId,
        created_by=actor["user_id"],
    )
    session.add(new_version)
    session.flush()

    for c in components:
        session.add(
            BomComponent(
                tenant_id=tenant_id,
                bom_version_id=new_version.id,
                line_no=c.line_no,
                component_product_id=c.component_product_id,
                component_sku=c.component_sku,
                quantity=c.quantity,
                uom=c.uom,
                scrap_percent=c.scrap_percent,
                is_alternate=c.is_alternate,
                alternate_for_line=c.alternate_for_line,
                notes=c.notes,
            )
        )

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="bom.version.revised", entity_type="bom", entity_id=str(id), meta={"from": source.version, "to": version_no})
    session.commit()

    return {**bom_repo.to_version_api(new_version), "components": bom_repo.components_api_of(tenant_id, new_version.id)}


@router.get("/boms/{id}/cost-rollup")
def cost_rollup(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("bom:read")), versionId: uuid_mod.UUID | None = None, asOf: date | None = None):
    tenant_id = actor["tenant_id"]
    bom = bom_repo.require_bom(tenant_id, id)
    as_of = asOf or date.today()

    if versionId:
        version = bom_repo.require_version(tenant_id, versionId, id)
    else:
        active = bom_repo.find_active_version(tenant_id, bom.product_id, as_of)
        version = active[1] if active else None
    if not version:
        raise not_found(f"Effective BOM version for {bom.product_sku} on {as_of.isoformat()}")

    ctx = TreeContext(tenant_id=tenant_id, as_of=as_of, max_depth=settings.bom_max_depth)
    tree = build_cost_tree(ctx, bom.product_sku, decimal_str(version.yield_percent), bom_repo.components_of(version.id))
    rollup = rollup_cost(tree)

    return {
        "bomId": str(id),
        "versionId": str(version.id),
        "version": version.version,
        "sku": bom.product_sku,
        "currency": settings.base_currency,
        "asOf": as_of.isoformat(),
        "unitCost": rollup.unit_cost,
        "lines": [
            {"lineNo": l.line_no, "sku": l.sku, "grossQuantity": l.gross_quantity, "unitCost": l.unit_cost, "extendedCost": l.extended_cost, "source": l.source}
            for l in rollup.lines
        ],
        "unpricedSkus": rollup.unpriced_skus,
    }


@router.get("/boms/{id}/explode")
def explode(id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission(*_BOM_LOOKUP_PERMISSIONS)), quantity: str = "1", asOf: date | None = None, versionId: uuid_mod.UUID | None = None):
    tenant_id = actor["tenant_id"]
    bom = bom_repo.require_bom(tenant_id, id)
    as_of = asOf or date.today()

    return bom_repo.explode_for_product(tenant_id, bom.product_id, quantity, as_of, version_id=versionId)
