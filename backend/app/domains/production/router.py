"""Production: BOM-driven manufacturing (create/plan/complete/bulk-upload),
finished-good item tracking (list/get/transfer/status-change), and assembly
stage checklist completion. Ported 1:1 (behavior) from the production
section of backend_py/app/routes/inventory_movements.py (lines 1355-2660 of
that file) - the part deferred during the earlier inventory-domain pass
because it depends on the BOM domain's `bom_repo.explode_for_product`, which
wasn't ported yet.

No PDF/QR/image-decode dependencies here - the one document-shaped thing
(testReportContentBase64) is a plain base64 file upload through
document_repo.upload_document/document_storage (already ported, no
weasyprint/PDF-rendering involved), so this domain ports in full with no
deferrals of its own.
"""

from __future__ import annotations

import csv
import io
import uuid as uuid_mod
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import or_

from app.core.auth import Actor, require_permission
from app.core.access_scope import assert_warehouse_in_scope, scope_query_by_warehouse
from app.core.audit import audit
from app.core.config import settings
from app.core.db import session
from app.core.errors import ProblemError, not_found, rule_violation
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.money import decimal_str, round_dp, to_decimal
from app.core.pagination import ListQuery, list_response, offset_of, parse_sort
from app.domains.production.schemas import (
    AdditionalComponentBody,
    ConsumedItemBody,
    FinishedGoodStatusBody,
    FinishedGoodTransferBody,
    ProductionBody,
    ProductionBulkUploadBody,
    ProductionCompleteBody,
    ProductionPlanBody,
    StageCompleteBody,
    UpdateProductionBody,
)
from app.models.document import Document
from app.models.finished_good_item import FinishedGoodItem
from app.models.grn_line import GrnLine
from app.models.inventory_item import InventoryItem
from app.models.product import Product
from app.models.production_consumption import ProductionConsumption
from app.models.production_consumption_item import ProductionConsumptionItem
from app.models.production_run import ProductionRun
from app.models.production_run_stage import STAGE_KEYS, STAGE_LABELS, ProductionRunStage
from app.models.stock_ledger import StockLedger
from app.models.warehouse import Warehouse
from app.services import bom_repo, document_repo, document_storage, inventory_ledger, product_repo, warehouse_repo
from app.services.availability import compute_availability
from app.services.inventory_ledger import LedgerPosting
from app.services.sequences import next_document_number
from app.services.uom import can_convert

router = APIRouter(prefix="/api/v1", tags=["production"])

_BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _to_base36(n: int) -> str:
    if n == 0:
        return "0"
    digits = []
    while n:
        n, r = divmod(n, 36)
        digits.append(_BASE36[r])
    return "".join(reversed(digits))


def _timestamp_ref(prefix: str) -> str:
    return f"{prefix}-{_to_base36(int(datetime.now(timezone.utc).timestamp() * 1000))}"


def _warehouse_name(warehouse_id) -> str | None:
    w = Warehouse.query.filter_by(id=warehouse_id).first()
    return w.name if w else None


def _to_run_api(r: ProductionRun, warehouse_name: str | None = None, product_name: str | None = None) -> dict:
    return {
        "id": str(r.id),
        "number": r.number,
        "productId": str(r.product_id),
        "sku": r.sku,
        "productName": product_name,
        "bomVersion": r.bom_version,
        "quantity": decimal_str(r.quantity),
        "uom": r.uom,
        "warehouseId": str(r.warehouse_id),
        "warehouseName": warehouse_name,
        "locationId": str(r.location_id) if r.location_id else None,
        "batchNo": r.batch_no,
        "expiryDate": r.expiry_date.isoformat() if r.expiry_date else None,
        "status": r.status,
        "notes": r.notes,
        "createdBy": r.created_by,
        "createdAt": r.created_at.isoformat() if r.created_at else None,
        "productionDate": r.production_date.isoformat() if r.production_date else None,
        "packId": r.pack_id,
        "shift": r.shift,
        "bmsMakeModel": r.bms_make_model,
        "screenType": r.screen_type,
        "bmsId": r.bms_id,
        "bluetoothId": r.bluetooth_id,
        "iotId": r.iot_id,
        "cellsName": r.cells_name,
        "cellsQuantity": r.cells_quantity,
        "seriesCount": r.series_count,
        "parallelCount": r.parallel_count,
        "enclosureName": r.enclosure_name,
        "chargeCapacity": r.charge_capacity,
        "dischargeCapacity": r.discharge_capacity,
        "brandingDetails": r.branding_details,
    }


def _to_stage_api(s: ProductionRunStage) -> dict:
    return {
        "id": str(s.id),
        "stageKey": s.stage_key,
        "label": STAGE_LABELS[s.stage_key],
        "sequence": s.sequence,
        "associateName": s.associate_name,
        "completedAt": s.completed_at.isoformat() if s.completed_at else None,
    }


# Maps ProductionBody's create-time "who did this" fields onto STAGE_KEYS.
# 'cell_testing' has no create-form field on purpose - see ProductionBody's
# comment above these fields.
_STAGE_CREATE_FIELDS = {
    "module_assembly": "moduleAssemblyBy",
    "cell_assembly": "cellAssemblyBy",
    "frp_cutting": "frpCuttingBy",
    "bms_sensing_cable_assembly": "bmsSensingCableAssemblyBy",
    "enclosure_assembly": "enclosureAssemblyBy",
    "qc_pdi": "qcPdiBy",
}


def _seed_stages(tenant_id, run_id, body: "ProductionBody | None" = None) -> list[ProductionRunStage]:
    """Seeds the full stage checklist, all unstarted - except any stage
    whose "who did this" field was filled in on the create form, which is
    stamped done right away. This is a bulk, unordered stamp: unlike
    complete_production_stage(), it does not enforce completing stages in
    sequence, since the create form is recording facts about work that
    already happened, not gating a live workflow."""
    now = datetime.now(timezone.utc)
    stages = []
    for i, key in enumerate(STAGE_KEYS, start=1):
        associate_name = getattr(body, _STAGE_CREATE_FIELDS[key]) if body and key in _STAGE_CREATE_FIELDS else None
        stages.append(
            ProductionRunStage(
                tenant_id=tenant_id,
                production_run_id=run_id,
                stage_key=key,
                sequence=i,
                associate_name=associate_name,
                completed_at=now if associate_name else None,
            )
        )
    session.add_all(stages)
    return stages


def _run_stages(tenant_id, run_id) -> list[ProductionRunStage]:
    return ProductionRunStage.query.filter_by(tenant_id=tenant_id, production_run_id=run_id).order_by(ProductionRunStage.sequence).all()


def _consumed_display(tenant_id, run_id) -> list[dict]:
    """The run's consumed-materials list, each row flagged `removable` -
    true only for an additional (beyond-BOM) component added through the
    add-additional-component endpoint below, never for one from the
    original create flow (which never wrote a production_consumption_items
    row, so there is nothing safe to reverse - see that endpoint's
    docstring). Detected by the reference_id scheme those draws post under
    ("<consumption id>:<draw index>"), batched into one query rather than
    one per row."""
    rows = ProductionConsumption.query.filter_by(tenant_id=tenant_id, production_run_id=run_id).order_by(ProductionConsumption.sku).all()
    additional_ids = [r.id for r in rows if r.is_additional]
    removable_ids: set[str] = set()
    if additional_ids:
        ledger_rows = StockLedger.query.filter(
            StockLedger.tenant_id == tenant_id,
            StockLedger.reference_type == "production",
            StockLedger.movement_type == "production_consume",
            or_(*[StockLedger.reference_id.like(f"{rid}:%") for rid in additional_ids]),
        ).all()
        for lr in ledger_rows:
            removable_ids.add(lr.reference_id.rsplit(":", 1)[0])
    product_ids = {c.product_id for c in rows}
    names_by_id = {p.id: p.name for p in Product.query.filter(Product.tenant_id == tenant_id, Product.id.in_(product_ids)).all()} if product_ids else {}
    return [
        {
            "id": str(c.id),
            "productId": str(c.product_id),
            "sku": c.sku,
            "productName": names_by_id.get(c.product_id),
            "quantity": decimal_str(c.quantity),
            "uom": c.uom,
            "unitCost": decimal_str(c.unit_cost) if c.unit_cost is not None else None,
            "isAdditional": c.is_additional,
            "removable": c.is_additional and str(c.id) in removable_ids,
        }
        for c in rows
    ]


def _run_test_report(tenant_id, run_id) -> dict | None:
    doc = Document.query.filter_by(tenant_id=tenant_id, related_type="production_run", related_id=str(run_id)).order_by(Document.created_at.desc()).first()
    if not doc:
        return None
    return {"id": str(doc.id), "filename": doc.filename, "url": document_storage.url_for(doc.id, doc.storage_key)}


def _to_finished_good_item_api(item: FinishedGoodItem) -> dict:
    return {
        "id": str(item.id),
        "inventoryId": item.inventory_id,
        "productionRunId": str(item.production_run_id) if item.production_run_id else None,
        "sourceInventoryItemId": str(item.source_inventory_item_id) if item.source_inventory_item_id else None,
        "productId": str(item.product_id),
        "sku": item.sku,
        "warehouseId": str(item.warehouse_id),
        "status": item.status,
        "kind": item.kind,
        "quantity": decimal_str(item.quantity),
        "uom": item.uom,
        "receivedDate": item.received_date.isoformat() if item.received_date else None,
        "batchNo": item.batch_no,
        "allocatedQty": decimal_str(item.allocated_qty),
        "shippedQty": decimal_str(item.shipped_qty),
        "availableQty": decimal_str(to_decimal(item.quantity) - to_decimal(item.allocated_qty) - to_decimal(item.shipped_qty)),
        "allocatedOrderId": str(item.allocated_order_id) if item.allocated_order_id else None,
        "allocatedOrderNumber": item.allocated_order_number,
        "locationId": str(item.location_id) if item.location_id else None,
        "locationCode": item.location_code,
        "createdAt": item.created_at.isoformat() if item.created_at else None,
    }


def _require_finished_good_item(tenant_id, id: uuid_mod.UUID) -> FinishedGoodItem:
    item = FinishedGoodItem.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not item:
        raise not_found("Finished good item")
    return item


# ============================================================================
# production posting
# ============================================================================


def _validate_additional_components(tenant_id, items: list[AdditionalComponentBody]) -> list[dict]:
    """Raw materials the operator is consuming beyond what the BOM calls for
    (rework, spillage, real-world substitution). Drawn FIFO at the quantity
    given, unless the operator hand-picked specific Inventory IDs via
    `items` - same optional manual-pick shape as the BOM side's
    `consumedItems`."""
    errors: list[dict] = []
    result: list[dict] = []
    for i, item in enumerate(items):
        product = product_repo.get_summary(tenant_id, item.productId)
        field = f"additionalComponents.{i}"
        if not product:
            errors.append({"field": field, "message": f"Product {item.productId} does not exist"})
            continue
        if product["type"] not in ("raw_material", "consumable"):
            errors.append({"field": field, "message": f"{product['sku']} is a {product['type'].replace('_', ' ')} — only raw materials and consumables can be added as extra production consumption"})
            continue
        if product["status"] != "active":
            errors.append({"field": field, "message": f"{product['sku']} is {product['status']} — only published products can be consumed"})
            continue
        if item.uom != product["uom"] and not can_convert(item.uom, product["uom"]):
            errors.append({"field": f"{field}.uom", "message": f"{item.uom} cannot be converted to {product['sku']}'s base unit {product['uom']}"})
            continue
        if item.items:
            wrong_product = [s for s in item.items if s.productId != item.productId]
            if wrong_product:
                errors.append({"field": f"{field}.items", "message": f"A selected Inventory ID does not belong to {product['sku']}"})
                continue
            picked = sum((to_decimal(s.quantity) for s in item.items), to_decimal(0))
            if picked < to_decimal(item.quantity):
                errors.append({"field": f"{field}.items", "message": f"{product['sku']}: selected {decimal_str(picked)} {product['uom']}, need at least {decimal_str(item.quantity)}"})
                continue
            if product["uom"] == "UNIT" and len(item.items) != int(to_decimal(item.quantity)):
                errors.append({"field": f"{field}.items", "message": f"{product['sku']} is tracked in whole units — select exactly {decimal_str(item.quantity)} Inventory ID(s), not {len(item.items)}"})
                continue
        result.append({"productId": str(item.productId), "sku": product["sku"], "uom": item.uom, "quantity": item.quantity, "level": 0, "items": item.items})
    if errors:
        joined = "; ".join(e["message"] for e in errors)
        raise rule_violation(f"Additional components list has {len(errors)} problem{'s' if len(errors) > 1 else ''}: {joined}", code="ADDITIONAL_COMPONENTS_INVALID", meta={"errors": errors})
    return result


def _actual_item_costs(tenant_id, item_ids: set) -> dict:
    """Each hand-picked Inventory ID's real, actual cost - straight off the
    GRN line it was received against (InventoryItem.grn_line_id is NOT
    NULL, so this always resolves for a genuine pick). Used instead of a
    product-wide historical average wherever the operator told us exactly
    which physical units they're consuming."""
    if not item_ids:
        return {}
    rows = session.query(InventoryItem.id, GrnLine.unit_price).join(GrnLine, GrnLine.id == InventoryItem.grn_line_id).filter(InventoryItem.tenant_id == tenant_id, InventoryItem.id.in_(item_ids)).all()
    return {str(item_id): to_decimal(unit_price) for item_id, unit_price in rows}


def _component_unit_cost(picked_items, item_costs: dict, fallback):
    """The real, weighted-actual cost of a component draw when the operator
    hand-picked specific Inventory IDs (each priced off its own GRN line via
    `item_costs`); falls back to the product's ledger-history weighted-
    average when nothing was picked - FIFO auto-consumption (no UI picks),
    or a sub-assembly consumed from a prior production run rather than a
    GRN receipt, neither of which name a specific Inventory ID here."""
    if not picked_items:
        return fallback
    total_qty = to_decimal(0)
    total_cost = to_decimal(0)
    for picked in picked_items:
        cost = item_costs.get(str(picked.itemId))
        if cost is None:
            continue
        qty = to_decimal(picked.quantity)
        total_qty += qty
        total_cost += cost * qty
    return total_cost / total_qty if total_qty > 0 else fallback


def _post_production(tenant_id, actor: Actor, body: ProductionBody, existing_run: ProductionRun | None = None) -> dict:
    """Shared by the single-production create route, the bulk-upload route,
    and Complete Production, so a production run posted any of those ways
    goes through the exact same BOM explosion, shortage checks, ledger
    postings and audit trail.

    existing_run, when given, is a 'planned' ProductionRun from Daily
    Production Planning (see complete_production) - it's updated in place
    and flipped to 'posted' instead of a new row being inserted, so the
    Production ID/number a planner already handed out stays the same one
    that ends up posted. body.productId/warehouseId/packId are still read
    normally below even in that case - complete_production builds `body`
    by copying those three off `existing_run` itself, since they're locked
    once planned and the request never carries them."""
    assert_warehouse_in_scope(actor, body.warehouseId)
    product = product_repo.get_summary(tenant_id, body.productId)
    if not product:
        raise not_found("Product")
    if product["type"] != "finished_good":
        raise rule_violation(f"{product['sku']} is a {product['type'].replace('_', ' ')} — only finished goods are produced against a BOM", code="NOT_A_FINISHED_GOOD")
    if product["batchTracked"] and not body.batchNo:
        raise rule_violation(f"{product['sku']} is batch tracked — a batch number is required for production", code="BATCH_REQUIRED")

    # Hard dependency: without the recipe we would produce from nothing.
    explosion = bom_repo.explode_for_product(tenant_id, body.productId, body.quantity, body.asOf or date.today())

    # Raw materials the operator adds beyond the BOM's own component list
    # (rework, spillage, a real-world substitution) - kept separate from
    # `explosion["requirements"]` throughout so BOM-required consumption
    # and extra consumption stay independently auditable.
    additional_requirements = _validate_additional_components(tenant_id, body.additionalComponents) if body.additionalComponents else []

    # When the operator hand-picks Inventory IDs, the consumed quantity is
    # the sum of what they selected per component (must cover the BOM
    # need); otherwise consumption is FIFO at the BOM-required quantity.
    selected_by_product: dict[str, object] = {}
    if body.consumedItems:
        for sel in body.consumedItems:
            key = str(sel.productId)
            selected_by_product[key] = selected_by_product.get(key, to_decimal(0)) + to_decimal(sel.quantity)
        sel_errors: list[dict] = []
        for requirement in explosion["requirements"]:
            picked = selected_by_product.get(requirement["productId"], to_decimal(0))
            if picked < to_decimal(requirement["quantity"]):
                sel_errors.append({"field": f"consumedItems.{requirement['sku']}", "message": f"{requirement['sku']}: selected {decimal_str(picked)} {requirement['uom']}, need at least {decimal_str(requirement['quantity'])}"})
        required_ids = {r["productId"] for r in explosion["requirements"]}
        for pid in selected_by_product:
            if pid not in required_ids:
                sel_errors.append({"field": "consumedItems", "message": f"A selected item is not a component of {product['sku']}"})
        if sel_errors:
            raise rule_violation(f"Component selection is incomplete: {'; '.join(e['message'] for e in sel_errors)}", code="COMPONENT_SELECTION_INVALID", meta={"errors": sel_errors})

    def consume_qty_for(requirement: dict):
        return selected_by_product.get(requirement["productId"], to_decimal(requirement["quantity"]))

    # Grouped the same way selected_by_product is, but keeping the picks
    # themselves (itemId + quantity) rather than just their sum - lets each
    # BOM requirement be priced off exactly what was picked for it.
    items_by_product: dict[str, list] = {}
    if body.consumedItems:
        for sel in body.consumedItems:
            items_by_product.setdefault(str(sel.productId), []).append(sel)

    product_ids = sorted({r["productId"] for r in explosion["requirements"]} | {r["productId"] for r in additional_requirements})
    for component_id in product_ids:
        inventory_ledger.lock_stock(tenant_id, uuid_mod.UUID(component_id), body.warehouseId)
    inventory_ledger.lock_stock(tenant_id, body.productId, body.warehouseId)

    # Costing: when the operator hand-picked specific Inventory IDs for a
    # component, price it off exactly those - each one's own real GRN
    # receipt cost, not an average. Only a component with no picks (FIFO
    # auto-consumption, or a sub-assembly drawn from a prior production run
    # rather than a GRN receipt) falls back to the product's ledger-history
    # weighted-average. Summed below into the finished good's own output
    # unit_cost, so Finished Goods valuation stops reading zero.
    picked_item_ids = {sel.itemId for sel in (body.consumedItems or [])} | {s.itemId for r in additional_requirements for s in (r.get("items") or [])}
    item_costs = _actual_item_costs(tenant_id, picked_item_ids)
    component_avg_costs = inventory_ledger.average_costs(tenant_id, [uuid_mod.UUID(pid) for pid in product_ids])

    shortages: list[dict] = []
    for requirement in explosion["requirements"]:
        buckets = inventory_ledger.bucket_totals(tenant_id, uuid_mod.UUID(requirement["productId"]), body.warehouseId)
        view = compute_availability(buckets)
        need = consume_qty_for(requirement)
        if need > to_decimal(view["availableToPromise"]):
            shortages.append({"field": f"requirements.{requirement['sku']}", "message": f"{requirement['sku']}: need {decimal_str(need)} {requirement['uom']}, only {decimal_str(view['availableToPromise'])} available"})
    for requirement in additional_requirements:
        buckets = inventory_ledger.bucket_totals(tenant_id, uuid_mod.UUID(requirement["productId"]), body.warehouseId)
        view = compute_availability(buckets)
        need = to_decimal(requirement["quantity"])
        if need > to_decimal(view["availableToPromise"]):
            shortages.append({"field": f"additionalComponents.{requirement['sku']}", "message": f"{requirement['sku']}: need {decimal_str(need)} {requirement['uom']}, only {decimal_str(view['availableToPromise'])} available"})
    if shortages:
        raise rule_violation(f"Cannot produce {decimal_str(body.quantity)} {body.uom} of {product['sku']} — {len(shortages)} component(s) short: {'; '.join(s['message'] for s in shortages)}", code="INSUFFICIENT_COMPONENTS", meta={"errors": shortages})

    if existing_run is not None:
        # Complete Production: finish an already-numbered 'planned' row in
        # place rather than minting a new number/row.
        run = existing_run
        number = run.number
        run.bom_version_id = explosion.get("versionId")
        run.bom_version = explosion.get("version")
        run.quantity = body.quantity
        run.uom = body.uom
        run.location_id = body.locationId
        run.batch_no = body.batchNo
        run.expiry_date = body.expiryDate
        run.notes = body.notes
        run.production_date = body.productionDate
        run.shift = body.shift
        run.bms_make_model = body.bmsMakeModel
        run.screen_type = body.screenType
        run.bms_id = body.bmsId
        run.bluetooth_id = body.bluetoothId
        run.iot_id = body.iotId
        run.cells_name = body.cellsName
        run.cells_quantity = body.cellsQuantity
        run.series_count = body.seriesCount
        run.parallel_count = body.parallelCount
        run.enclosure_name = body.enclosureName
        run.charge_capacity = body.chargeCapacity
        run.discharge_capacity = body.dischargeCapacity
        run.branding_details = body.brandingDetails
        run.status = "posted"
    else:
        number = next_document_number(tenant_id, "PRD", pad=4, start=1000)
        run = ProductionRun(
            tenant_id=tenant_id,
            number=number,
            product_id=body.productId,
            sku=product["sku"],
            bom_version_id=explosion.get("versionId"),
            bom_version=explosion.get("version"),
            quantity=body.quantity,
            uom=body.uom,
            warehouse_id=body.warehouseId,
            location_id=body.locationId,
            batch_no=body.batchNo,
            expiry_date=body.expiryDate,
            notes=body.notes,
            created_by=str(actor["user_id"]),
            production_date=body.productionDate,
            pack_id=body.packId,
            shift=body.shift,
            bms_make_model=body.bmsMakeModel,
            screen_type=body.screenType,
            bms_id=body.bmsId,
            bluetooth_id=body.bluetoothId,
            iot_id=body.iotId,
            cells_name=body.cellsName,
            cells_quantity=body.cellsQuantity,
            series_count=body.seriesCount,
            parallel_count=body.parallelCount,
            enclosure_name=body.enclosureName,
            charge_capacity=body.chargeCapacity,
            discharge_capacity=body.dischargeCapacity,
            branding_details=body.brandingDetails,
        )
        session.add(run)
    session.flush()

    _seed_stages(tenant_id, run.id, body)

    if body.testReportContentBase64:
        document_repo.upload_document(
            tenant_id,
            filename=body.testReportFilename or f"{number}-test-report",
            content_type=body.testReportContentType or "application/pdf",
            content_base64=body.testReportContentBase64,
            related_type="production_run",
            related_id=str(run.id),
            created_by=str(actor["user_id"]),
        )

    total_material_cost = to_decimal(0)

    for requirement in explosion["requirements"]:
        consume_qty = consume_qty_for(requirement)
        fallback_cost = component_avg_costs.get(requirement["productId"], to_decimal(0))
        avg_cost = _component_unit_cost(items_by_product.get(requirement["productId"]), item_costs, fallback_cost)
        unit_cost = decimal_str(round_dp(avg_cost, 4))
        total_material_cost += avg_cost * consume_qty

        # Consumption is drawn from the bins that actually hold the stock,
        # soonest expiry first - a location-less negative would leave the
        # bins reading full while a phantom balance went negative.
        sources = inventory_ledger.available_by_location(tenant_id, uuid_mod.UUID(requirement["productId"]), body.warehouseId)
        draws = inventory_ledger.draw_from(sources, consume_qty)
        for draw_index, draw in enumerate(draws):
            inventory_ledger.post(
                LedgerPosting(
                    tenant_id=tenant_id,
                    product_id=requirement["productId"],
                    sku=requirement["sku"],
                    warehouse_id=body.warehouseId,
                    location_id=draw.source.location_id if draw.source else None,
                    batch_no=draw.source.batch_no if draw.source else None,
                    expiry_date=draw.source.expiry_date if draw.source else None,
                    quantity=decimal_str(-to_decimal(draw.quantity)),
                    uom=requirement["uom"],
                    bucket="available",
                    movement_type="production_consume",
                    reference_type="production",
                    # The index keeps each draw distinct while a redelivery
                    # still collapses.
                    reference_id=f"{run.id}:{requirement['productId']}:{draw_index}",
                    reference_no=number,
                    unit_cost=unit_cost,
                    currency=settings.base_currency,
                    reason=f"Consumed for {product['sku']} production {number}" + (f" (batch {draw.source.batch_no})" if draw.source and draw.source.batch_no else ""),
                    actor_id=str(actor["user_id"]),
                )
            )
        session.add(ProductionConsumption(tenant_id=tenant_id, production_run_id=run.id, product_id=requirement["productId"], sku=requirement["sku"], quantity=decimal_str(consume_qty), uom=requirement["uom"], unit_cost=unit_cost, is_additional=False))

    for requirement in additional_requirements:
        consume_qty = to_decimal(requirement["quantity"])
        fallback_cost = component_avg_costs.get(requirement["productId"], to_decimal(0))
        avg_cost = _component_unit_cost(requirement.get("items"), item_costs, fallback_cost)
        unit_cost = decimal_str(round_dp(avg_cost, 4))
        total_material_cost += avg_cost * consume_qty

        sources = inventory_ledger.available_by_location(tenant_id, uuid_mod.UUID(requirement["productId"]), body.warehouseId)
        draws = inventory_ledger.draw_from(sources, consume_qty)
        for draw_index, draw in enumerate(draws):
            inventory_ledger.post(
                LedgerPosting(
                    tenant_id=tenant_id,
                    product_id=requirement["productId"],
                    sku=requirement["sku"],
                    warehouse_id=body.warehouseId,
                    location_id=draw.source.location_id if draw.source else None,
                    batch_no=draw.source.batch_no if draw.source else None,
                    expiry_date=draw.source.expiry_date if draw.source else None,
                    quantity=decimal_str(-to_decimal(draw.quantity)),
                    uom=requirement["uom"],
                    bucket="available",
                    movement_type="production_consume",
                    reference_type="production",
                    reference_id=f"{run.id}:{requirement['productId']}:additional:{draw_index}",
                    reference_no=number,
                    unit_cost=unit_cost,
                    currency=settings.base_currency,
                    reason=f"Additional consumption (beyond BOM) for {product['sku']} production {number}" + (f" (batch {draw.source.batch_no})" if draw.source and draw.source.batch_no else ""),
                    actor_id=str(actor["user_id"]),
                )
            )
        session.add(ProductionConsumption(tenant_id=tenant_id, production_run_id=run.id, product_id=requirement["productId"], sku=requirement["sku"], quantity=decimal_str(consume_qty), uom=requirement["uom"], unit_cost=unit_cost, is_additional=True))

    # The finished good's own unit_cost is the total cost of everything just
    # consumed for it (BOM + additional components, each priced at its own
    # weighted-average cost above) spread across the output quantity -
    # ProductionRun itself still tracks no unit_cost/value of its own (see
    # _to_run_api); this only feeds the StockLedger postings below, which is
    # all compute_valuation() reads.
    #
    # Output gets one FinishedGoodItem per physical unit for a UOM=UNIT
    # product (kind='piece'), same serialized-vs-lot split GRN receiving
    # makes (_is_serial_uom/_create_inventory_for_line, grns.py) - one lot
    # row for the whole quantity otherwise. Each item gets its OWN ledger
    # posting (reference_id = the item's id, not the run's) rather than one
    # aggregate posting for the run, so GET /inventory/ledger?referenceId=
    # gives each FG-ID a real, individual movement history. The sum of the
    # per-item postings equals the old single posting, so StockBalance ends
    # up identical either way.
    output_qty = to_decimal(body.quantity)
    is_serial_output = body.uom.upper() == "UNIT"
    if is_serial_output and output_qty != output_qty.to_integral_value():
        raise rule_violation(f"{product['sku']} is tracked in whole units — quantity must be a whole number", code="QUANTITY_NOT_WHOLE")
    fg_unit_cost = decimal_str(round_dp(total_material_cost / output_qty, 4)) if output_qty > 0 else decimal_str(0)
    unit_count = int(output_qty) if is_serial_output else 1
    fg_ids = warehouse_repo.reserve_finished_good_ids(tenant_id, unit_count)
    fg_items: list[FinishedGoodItem] = []
    for i in range(unit_count):
        item_qty = to_decimal(1) if is_serial_output else output_qty
        fg_item = FinishedGoodItem(
            tenant_id=tenant_id,
            inventory_id=fg_ids[i],
            production_run_id=run.id,
            product_id=body.productId,
            sku=product["sku"],
            warehouse_id=body.warehouseId,
            kind="piece" if is_serial_output else "lot",
            quantity=decimal_str(item_qty),
            uom=body.uom,
            received_date=body.productionDate or date.today(),
            batch_no=body.batchNo,
            location_id=body.locationId,
        )
        session.add(fg_item)
        fg_items.append(fg_item)
    session.flush()

    for fg_item in fg_items:
        inventory_ledger.post(
            LedgerPosting(
                tenant_id=tenant_id,
                product_id=body.productId,
                sku=product["sku"],
                warehouse_id=body.warehouseId,
                location_id=body.locationId,
                batch_no=body.batchNo,
                expiry_date=body.expiryDate.isoformat() if body.expiryDate else None,
                quantity=decimal_str(fg_item.quantity),
                uom=body.uom,
                bucket="available",
                movement_type="production_output",
                reference_type="production",
                reference_id=str(fg_item.id),
                reference_no=number,
                unit_cost=fg_unit_cost,
                currency=settings.base_currency,
                reason=f"Production run {number}",
                actor_id=str(actor["user_id"]),
            )
        )

    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="inventory.production.posted",
        entity_type="production-run",
        entity_id=str(run.id),
        meta={"number": number, "sku": product["sku"], "quantity": body.quantity, "bomVersion": explosion.get("version"), "components": len(explosion["requirements"]), "additionalComponents": len(additional_requirements)},
    )

    # Warehouse's own Inventory-ID ledger (piece/lot QC tracking) must stay
    # honest too - direct call in place of Node's ProductionPosted event,
    # same transaction.
    warehouse_repo.consume_inventory_items_for_production(
        tenant_id,
        production_run_id=run.id,
        number=number,
        warehouse_id=body.warehouseId,
        consumed=[{"productId": r["productId"], "sku": r["sku"], "quantity": decimal_str(consume_qty_for(r)), "uom": r["uom"]} for r in explosion["requirements"]],
        consumed_items=[{"itemId": str(s.itemId), "quantity": s.quantity} for s in body.consumedItems] if body.consumedItems else None,
    )
    if additional_requirements:
        additional_consumed_items = [{"itemId": str(s.itemId), "quantity": s.quantity} for r in additional_requirements for s in (r.get("items") or [])]
        warehouse_repo.consume_inventory_items_for_production(
            tenant_id,
            production_run_id=run.id,
            number=number,
            warehouse_id=body.warehouseId,
            consumed=[{"productId": r["productId"], "sku": r["sku"], "quantity": r["quantity"], "uom": r["uom"]} for r in additional_requirements],
            consumed_items=additional_consumed_items or None,
        )

    session.commit()

    return {
        "id": str(run.id),
        "number": number,
        "consumed": [{**r, "isAdditional": False} for r in explosion["requirements"]] + [{**r, "isAdditional": True} for r in additional_requirements],
    }


@router.post("/inventory/production", status_code=201)
def post_production(body: ProductionBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("inventory:produce"))):
    tenant_id = actor["tenant_id"]

    def _do():
        return 201, _post_production(tenant_id, actor, body)

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


@router.post("/inventory/production/plan", status_code=201)
def plan_production(body: ProductionPlanBody, actor: Actor = Depends(require_permission("inventory:produce"))):
    """Daily Production Planning: bulk-create bare 'planned' ProductionRun
    rows for one warehouse/date, one per {finishedGood, packId} row the
    planner listed - no BOM explosion, no consumption, no stock movement.
    Each gets its real PRD-number now, so the number a planner hands out
    today is the same one that ends up posted once Complete Production
    (complete_production, below) finishes it."""
    tenant_id = actor["tenant_id"]
    assert_warehouse_in_scope(actor, body.warehouseId)

    warehouse_name = _warehouse_name(body.warehouseId)
    runs: list[ProductionRun] = []
    for item in body.items:
        product = product_repo.get_summary(tenant_id, item.productId)
        if not product:
            raise not_found("Product")
        if product["type"] != "finished_good":
            raise rule_violation(f"{product['sku']} is a {product['type'].replace('_', ' ')} — only finished goods can be planned for production", code="NOT_A_FINISHED_GOOD")

        number = next_document_number(tenant_id, "PRD", pad=4, start=1000)
        run = ProductionRun(
            tenant_id=tenant_id,
            number=number,
            product_id=item.productId,
            sku=product["sku"],
            quantity="1",
            uom="UNIT",
            warehouse_id=body.warehouseId,
            production_date=body.productionDate,
            pack_id=item.packId,
            status="planned",
            created_by=str(actor["user_id"]),
        )
        session.add(run)
        session.flush()
        audit(
            tenant_id=tenant_id,
            actor_id=actor["user_id"],
            actor_email=actor["email"],
            action="inventory.production.planned",
            entity_type="production-run",
            entity_id=str(run.id),
            meta={"number": number, "sku": product["sku"], "warehouseId": str(body.warehouseId), "productionDate": body.productionDate.isoformat()},
        )
        runs.append(run)

    session.commit()
    return JSONResponse(status_code=201, content={"data": [_to_run_api(r, warehouse_name, product_repo.get_summary(tenant_id, r.product_id)["name"]) for r in runs]})


@router.post("/inventory/production/{id}/complete")
def complete_production(id: uuid_mod.UUID, body: ProductionCompleteBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("inventory:produce"))):
    """Complete Production: finishes a 'planned' row from Daily Production
    Planning - runs the exact same BOM-explode/consume/create-FG logic
    post_production runs for a direct create (see _post_production's
    existing_run branch), against the already-planned product/warehouse/
    pack ID rather than ones supplied in this request, and flips the row's
    status from 'planned' to 'posted' in place."""
    tenant_id = actor["tenant_id"]

    run = ProductionRun.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not run:
        raise not_found("Production run")
    if run.status != "planned":
        raise rule_violation(f"{run.number} is {run.status} and cannot be completed — only a planned run can be", code="PRODUCTION_NOT_PLANNED")
    assert_warehouse_in_scope(actor, run.warehouse_id)

    full_body = ProductionBody(
        productId=run.product_id,
        warehouseId=run.warehouse_id,
        quantity=run.quantity,
        uom=run.uom,
        packId=run.pack_id,
        locationId=body.locationId,
        batchNo=body.batchNo,
        expiryDate=body.expiryDate,
        asOf=body.asOf,
        notes=body.notes,
        consumedItems=body.consumedItems,
        additionalComponents=body.additionalComponents,
        productionDate=body.productionDate or run.production_date,
        shift=body.shift,
        bmsMakeModel=body.bmsMakeModel,
        screenType=body.screenType,
        bmsId=body.bmsId,
        bluetoothId=body.bluetoothId,
        iotId=body.iotId,
        cellsName=body.cellsName,
        cellsQuantity=body.cellsQuantity,
        seriesCount=body.seriesCount,
        parallelCount=body.parallelCount,
        enclosureName=body.enclosureName,
        chargeCapacity=body.chargeCapacity,
        dischargeCapacity=body.dischargeCapacity,
        brandingDetails=body.brandingDetails,
        testReportFilename=body.testReportFilename,
        testReportContentType=body.testReportContentType,
        testReportContentBase64=body.testReportContentBase64,
        moduleAssemblyBy=body.moduleAssemblyBy,
        cellAssemblyBy=body.cellAssemblyBy,
        frpCuttingBy=body.frpCuttingBy,
        bmsSensingCableAssemblyBy=body.bmsSensingCableAssemblyBy,
        enclosureAssemblyBy=body.enclosureAssemblyBy,
        qcPdiBy=body.qcPdiBy,
    )

    def _do():
        return 200, _post_production(tenant_id, actor, full_body, existing_run=run)

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


# One row per production run. FIFO auto-consumption only - manual Inventory-ID
# picking (consumedItems) isn't a spreadsheet workflow, so bulk upload always
# consumes at the BOM-required quantity, same as the single-create route does
# when consumedItems is omitted. additionalComponents is a "SKU:QTY:UOM"
# list, pipe-separated for more than one extra component.
PRODUCTION_BULK_UPLOAD_REQUIRED_COLUMNS = ["productSku", "quantity", "uom", "warehouseCode"]
PRODUCTION_BULK_UPLOAD_ALL_COLUMNS = ["productSku", "quantity", "uom", "warehouseCode", "locationCode", "batchNo", "expiryDate", "asOf", "notes", "additionalComponents"]


@router.post("/inventory/production/bulk-upload")
def bulk_upload_production(body: ProductionBulkUploadBody, actor: Actor = Depends(require_permission("inventory:produce"))):
    """Posts many production runs from one CSV in a single request - one row
    per run. A bad row is reported as an error and skipped, it never fails
    rows that already validated fine."""
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in PRODUCTION_BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    # Resolved up front for the whole file: the produced SKU, every
    # additionalComponents SKU, the warehouse and the location.
    parsed = [(row_number, {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k}) for row_number, raw_row in enumerate(reader, start=2)]

    def _component_skus(raw: str) -> list[str]:
        """SKUs from a well-formed SKU:QTY:UOM entry. Malformed entries are
        left alone here - the row loop still reports them one by one."""
        out = []
        for entry in (raw or "").split("|"):
            parts = entry.strip().split(":")
            if entry.strip() and len(parts) == 3:
                out.append(parts[0].strip())
        return out

    all_skus = [r.get("productSku") or "" for _, r in parsed]
    for _, r in parsed:
        all_skus.extend(_component_skus(r.get("additionalComponents") or ""))
    products_by_sku = product_repo.find_by_skus(tenant_id, all_skus)
    warehouses_by_code = warehouse_repo.find_warehouses_by_codes(tenant_id, [r.get("warehouseCode") or "" for _, r in parsed])
    locations_by_key = warehouse_repo.find_locations_by_codes(
        [(wh.id, r.get("locationCode") or "") for _, r in parsed if (wh := warehouses_by_code.get((r.get("warehouseCode") or "").upper())) and r.get("locationCode")]
    )

    results = []
    for row_number, row in parsed:
        if not any(row.values()):
            continue
        label = row.get("productSku") or f"(row {row_number})"
        errors: list[str] = []

        sku = row.get("productSku") or ""
        product = products_by_sku.get(sku.upper()) if sku else None
        if not sku:
            errors.append("productSku is required")
        elif not product:
            errors.append(f"Product SKU '{sku}' not found")

        warehouse_code = row.get("warehouseCode") or ""
        warehouse = warehouses_by_code.get(warehouse_code.upper()) if warehouse_code else None
        if not warehouse_code:
            errors.append("warehouseCode is required")
        elif not warehouse:
            errors.append(f"Warehouse code '{warehouse_code}' not found")

        location_id = None
        location_code = row.get("locationCode") or ""
        if location_code and warehouse:
            loc = locations_by_key.get((warehouse.id, location_code.upper()))
            if not loc:
                errors.append(f"Location code '{location_code}' not found in warehouse {warehouse_code}")
            else:
                location_id = loc.id

        additional_components = []
        raw_additional = row.get("additionalComponents") or ""
        if raw_additional:
            for entry in raw_additional.split("|"):
                entry = entry.strip()
                if not entry:
                    continue
                parts = entry.split(":")
                if len(parts) != 3:
                    errors.append(f"additionalComponents entry '{entry}' must be SKU:QTY:UOM")
                    continue
                add_sku, add_qty, add_uom = (p.strip() for p in parts)
                add_product = products_by_sku.get(add_sku.upper())
                if not add_product:
                    errors.append(f"additionalComponents: SKU '{add_sku}' not found")
                    continue
                try:
                    additional_components.append(AdditionalComponentBody(productId=add_product.id, quantity=add_qty, uom=add_uom or add_product.uom))
                except ValidationError as exc:
                    errors.append(f"additionalComponents '{entry}': {exc.errors()[0].get('msg', 'invalid data')}")

        if errors:
            results.append({"row": row_number, "label": label, "status": "error", "error": "; ".join(errors), "rowData": row})
            continue

        try:
            production_body = ProductionBody(
                productId=product.id,
                quantity=row.get("quantity") or "",
                uom=row.get("uom") or "",
                warehouseId=warehouse.id,
                locationId=location_id,
                batchNo=row.get("batchNo") or None,
                expiryDate=date.fromisoformat(row["expiryDate"]) if row.get("expiryDate") else None,
                asOf=date.fromisoformat(row["asOf"]) if row.get("asOf") else None,
                notes=row.get("notes") or None,
                additionalComponents=additional_components or None,
            )
        except (ValidationError, ValueError) as exc:
            message = exc.errors()[0].get("msg", "invalid data") if isinstance(exc, ValidationError) else str(exc)
            results.append({"row": row_number, "label": label, "status": "error", "error": message, "rowData": row})
            continue

        try:
            result = _post_production(tenant_id, actor, production_body)
            results.append({"row": row_number, "label": label, "status": "success", "runNumber": result["number"], "rowData": row})
        except ProblemError as exc:
            session.rollback()
            results.append({"row": row_number, "label": label, "status": "error", "error": exc.detail, "rowData": row})
        except Exception as exc:  # noqa: BLE001 - one bad row must not fail the whole batch
            session.rollback()
            results.append({"row": row_number, "label": label, "status": "error", "error": str(exc), "rowData": row})

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    return {
        "summary": {"totalRows": len(results), "successCount": success_count, "errorCount": error_count},
        "results": [
            {"row": r["row"], "label": r["label"], "status": r["status"], "runNumber": r.get("runNumber"), "error": r.get("error"), "rowData": r["rowData"] if r["status"] == "error" else {}}
            for r in results
        ],
    }


@router.get("/inventory/production")
def list_production(
    actor: Actor = Depends(require_permission("inventory:read")),
    query: ListQuery = Depends(),
    productId: uuid_mod.UUID | None = None,
    warehouseId: uuid_mod.UUID | None = None,
    status: str | None = None,
    productionDateFrom: str | None = None,
    productionDateTo: str | None = None,
):
    """Production ledger - every finished-goods run ever posted, whatever
    became of the output afterwards. A record of what was made, not of what
    is on hand."""
    tenant_id = actor["tenant_id"]

    q = ProductionRun.query.filter(ProductionRun.tenant_id == tenant_id)
    if productId:
        q = q.filter(ProductionRun.product_id == productId)
    if warehouseId:
        assert_warehouse_in_scope(actor, warehouseId)
        q = q.filter(ProductionRun.warehouse_id == warehouseId)
    else:
        q = scope_query_by_warehouse(q, ProductionRun.warehouse_id, actor)
    if status:
        q = q.filter(ProductionRun.status == status)
    if productionDateFrom:
        try:
            q = q.filter(ProductionRun.production_date >= date.fromisoformat(productionDateFrom))
        except ValueError:
            raise rule_violation("productionDateFrom must be an ISO date (YYYY-MM-DD)", code="INVALID_DATE")
    if productionDateTo:
        try:
            q = q.filter(ProductionRun.production_date <= date.fromisoformat(productionDateTo))
        except ValueError:
            raise rule_violation("productionDateTo must be an ISO date (YYYY-MM-DD)", code="INVALID_DATE")
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(ProductionRun.number.ilike(like), ProductionRun.sku.ilike(like), ProductionRun.pack_id.ilike(like)))

    total = q.count()
    order = parse_sort(query.sort, ["number", "created_at", "quantity", "sku"], ("created_at", "desc"))
    for col, direction in order:
        column = getattr(ProductionRun, col)
        q = q.order_by(column.desc() if direction == "desc" else column.asc())
    rows = q.limit(query.limit).offset(offset_of(query)).all()

    # One query for the whole page rather than one per row.
    names_by_id = {str(w.id): w.name for w in Warehouse.query.filter(Warehouse.id.in_({r.warehouse_id for r in rows})).all()}
    product_names_by_id = {str(p.id): p.name for p in Product.query.filter(Product.id.in_({r.product_id for r in rows})).all()}
    return list_response([_to_run_api(r, names_by_id.get(str(r.warehouse_id)), product_names_by_id.get(str(r.product_id))) for r in rows], query, total)


@router.get("/inventory/production/{id}")
def get_production(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("inventory:read"))):
    """One production run with the raw materials it consumed."""
    tenant_id = actor["tenant_id"]
    run = ProductionRun.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not run:
        raise not_found("Production run")
    assert_warehouse_in_scope(actor, run.warehouse_id)

    product = Product.query.filter_by(tenant_id=tenant_id, id=run.product_id).first()
    result = _to_run_api(run, _warehouse_name(run.warehouse_id), product.name if product else None)
    result["consumed"] = _consumed_display(tenant_id, id)
    result["stages"] = [_to_stage_api(s) for s in _run_stages(tenant_id, id)]
    result["testReport"] = _run_test_report(tenant_id, id)
    # The finished-good units this run actually produced - each one gets its
    # own FG-ID (see the comment on FinishedGoodItem creation, further down
    # this file), one row per physical unit for a UOM=UNIT product, one lot
    # row otherwise.
    finished_items = FinishedGoodItem.query.filter_by(tenant_id=tenant_id, production_run_id=id).order_by(FinishedGoodItem.inventory_id).all()
    result["finishedGoods"] = [_to_finished_good_item_api(i) for i in finished_items]
    return result


@router.patch("/inventory/production/{id}")
def update_production(id: uuid_mod.UUID, body: UpdateProductionBody, actor: Actor = Depends(require_permission("inventory:produce"))):
    """Corrects the descriptive battery-pack traceability fields (and
    notes/test report) on an already-posted run - see UpdateProductionBody
    for exactly what is and isn't in scope, and why."""
    tenant_id = actor["tenant_id"]

    run = ProductionRun.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not run:
        raise not_found("Production run")
    if run.status == "reversed":
        raise rule_violation(f"{run.number} has been reversed and can no longer be edited", code="PRODUCTION_RUN_REVERSED")

    assert_warehouse_in_scope(actor, run.warehouse_id)
    run.notes = body.notes
    run.production_date = body.productionDate
    run.pack_id = body.packId
    run.shift = body.shift
    run.bms_make_model = body.bmsMakeModel
    run.screen_type = body.screenType
    run.bms_id = body.bmsId
    run.bluetooth_id = body.bluetoothId
    run.iot_id = body.iotId
    run.cells_name = body.cellsName
    run.cells_quantity = body.cellsQuantity
    run.series_count = body.seriesCount
    run.parallel_count = body.parallelCount
    run.enclosure_name = body.enclosureName
    run.charge_capacity = body.chargeCapacity
    run.discharge_capacity = body.dischargeCapacity
    run.branding_details = body.brandingDetails

    if body.testReportContentBase64:
        document_repo.upload_document(
            tenant_id,
            filename=body.testReportFilename or f"{run.number}-test-report",
            content_type=body.testReportContentType or "application/pdf",
            content_base64=body.testReportContentBase64,
            related_type="production_run",
            related_id=str(run.id),
            created_by=str(actor["user_id"]),
        )

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="inventory.production.updated", entity_type="production-run", entity_id=str(run.id), meta={"number": run.number})
    session.commit()

    result = _to_run_api(run, _warehouse_name(run.warehouse_id))
    result["consumed"] = _consumed_display(tenant_id, id)
    result["stages"] = [_to_stage_api(s) for s in _run_stages(tenant_id, id)]
    result["testReport"] = _run_test_report(tenant_id, id)
    return result


@router.post("/inventory/production/{id}/additional-components")
def add_production_additional_component(id: uuid_mod.UUID, body: AdditionalComponentBody, actor: Actor = Depends(require_permission("inventory:produce"))):
    """Adds one raw material beyond the BOM to an already-posted run -
    consumes stock right away, same as _post_production's own additional-
    components block, but scoped to a single new line and recorded with
    enough per-item detail (production_consumption_items) that it can later
    be safely removed via the endpoint below. Components added by the
    original create flow have no such record and can never be removed this
    way - see _consumed_display."""
    tenant_id = actor["tenant_id"]

    run = ProductionRun.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not run:
        raise not_found("Production run")
    if run.status == "reversed":
        raise rule_violation(f"{run.number} has been reversed and can no longer be edited", code="PRODUCTION_RUN_REVERSED")
    assert_warehouse_in_scope(actor, run.warehouse_id)

    [validated] = _validate_additional_components(tenant_id, [body])

    inventory_ledger.lock_stock(tenant_id, body.productId, run.warehouse_id)
    buckets = inventory_ledger.bucket_totals(tenant_id, body.productId, run.warehouse_id)
    view = compute_availability(buckets)
    need = to_decimal(validated["quantity"])
    if need > to_decimal(view["availableToPromise"]):
        raise rule_violation(f"{validated['sku']}: need {decimal_str(need)} {validated['uom']}, only {decimal_str(view['availableToPromise'])} available", code="INSUFFICIENT_COMPONENTS")

    # Priced the same way as _post_production's own additional-components
    # block - the picked Inventory IDs' own real GRN cost when given, else
    # the material's ledger-history weighted-average. This run's finished
    # good already posted its output unit_cost when it was produced, so a
    # component added here after the fact isn't rolled back into it.
    fallback_cost = inventory_ledger.average_costs(tenant_id, [body.productId]).get(str(body.productId), to_decimal(0))
    item_costs = _actual_item_costs(tenant_id, {sel.itemId for sel in (body.items or [])})
    avg_cost = _component_unit_cost(body.items, item_costs, fallback_cost)
    unit_cost = decimal_str(round_dp(avg_cost, 4))

    consumption = ProductionConsumption(tenant_id=tenant_id, production_run_id=run.id, product_id=body.productId, sku=validated["sku"], quantity=decimal_str(need), uom=validated["uom"], unit_cost=unit_cost, is_additional=True)
    session.add(consumption)
    session.flush()

    sources = inventory_ledger.available_by_location(tenant_id, body.productId, run.warehouse_id)
    draws = inventory_ledger.draw_from(sources, need)
    for draw_index, draw in enumerate(draws):
        inventory_ledger.post(
            LedgerPosting(
                tenant_id=tenant_id,
                product_id=body.productId,
                sku=validated["sku"],
                warehouse_id=run.warehouse_id,
                location_id=draw.source.location_id if draw.source else None,
                batch_no=draw.source.batch_no if draw.source else None,
                expiry_date=draw.source.expiry_date if draw.source else None,
                quantity=decimal_str(-to_decimal(draw.quantity)),
                uom=validated["uom"],
                bucket="available",
                movement_type="production_consume",
                reference_type="production",
                reference_id=f"{consumption.id}:{draw_index}",
                reference_no=run.number,
                unit_cost=unit_cost,
                currency=settings.base_currency,
                reason=f"Additional consumption (beyond BOM, added via edit) for {run.sku} production {run.number}" + (f" (batch {draw.source.batch_no})" if draw.source and draw.source.batch_no else ""),
                actor_id=str(actor["user_id"]),
            )
        )

    item_draws = warehouse_repo.consume_inventory_items_for_production(
        tenant_id,
        production_run_id=run.id,
        number=run.number,
        warehouse_id=run.warehouse_id,
        consumed=[{"productId": str(body.productId), "sku": validated["sku"], "quantity": decimal_str(need), "uom": validated["uom"]}],
        consumed_items=[{"itemId": str(s.itemId), "quantity": s.quantity} for s in body.items] if body.items else None,
    )
    for d in item_draws:
        session.add(ProductionConsumptionItem(tenant_id=tenant_id, production_consumption_id=consumption.id, inventory_item_id=d["itemId"], quantity=d["quantity"]))

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="inventory.production.additional_component_added", entity_type="production-run", entity_id=str(run.id), meta={"sku": validated["sku"], "quantity": decimal_str(need), "uom": validated["uom"]})
    session.commit()

    return _consumed_display(tenant_id, run.id)


@router.delete("/inventory/production/{id}/additional-components/{consumption_id}")
def remove_production_additional_component(id: uuid_mod.UUID, consumption_id: uuid_mod.UUID, actor: Actor = Depends(require_permission("inventory:produce"))):
    """Reverses one additional component previously added via the endpoint
    above - the exact opposite of it: reverses the stock-ledger draws it
    posted (inventory_ledger.reverse, same mechanism GRN cancellation uses)
    and credits back InventoryItem.consumed_qty for exactly what it drew.
    Only possible because that add recorded per-item detail in
    production_consumption_items; a component from the original create flow
    never did, so there is nothing here to safely reverse it against."""
    tenant_id = actor["tenant_id"]

    run = ProductionRun.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not run:
        raise not_found("Production run")
    if run.status == "reversed":
        raise rule_violation(f"{run.number} has been reversed and can no longer be edited", code="PRODUCTION_RUN_REVERSED")
    assert_warehouse_in_scope(actor, run.warehouse_id)

    consumption = ProductionConsumption.query.filter_by(tenant_id=tenant_id, id=consumption_id, production_run_id=id, is_additional=True).first()
    if not consumption:
        raise not_found("Additional component")

    ledger_rows = StockLedger.query.filter(
        StockLedger.tenant_id == tenant_id,
        StockLedger.reference_type == "production",
        StockLedger.movement_type == "production_consume",
        StockLedger.reference_id.like(f"{consumption.id}:%"),
    ).all()
    item_rows = ProductionConsumptionItem.query.filter_by(tenant_id=tenant_id, production_consumption_id=consumption.id).all()
    if not ledger_rows and not item_rows:
        raise rule_violation(f"{consumption.sku} was added before this feature existed and can't be safely removed", code="ADDITIONAL_COMPONENT_NOT_REMOVABLE")

    already_reversed = {
        row.reverses_id
        for row in StockLedger.query.filter(StockLedger.tenant_id == tenant_id, StockLedger.movement_type == "reversal", StockLedger.reverses_id.in_([r.id for r in ledger_rows])).all()
    }
    for row in ledger_rows:
        if row.id in already_reversed:
            continue
        original = LedgerPosting(
            tenant_id=tenant_id,
            product_id=row.product_id,
            sku=row.sku,
            warehouse_id=row.warehouse_id,
            location_id=row.location_id,
            batch_no=row.batch_no,
            expiry_date=row.expiry_date.isoformat() if row.expiry_date else None,
            quantity=decimal_str(row.quantity),
            uom=row.uom,
            bucket=row.bucket,
            movement_type=row.movement_type,
            reference_type=row.reference_type,
            reference_id=row.reference_id,
            reference_no=row.reference_no,
            unit_cost=decimal_str(row.unit_cost) if row.unit_cost is not None else None,
            currency=row.currency,
        )
        inventory_ledger.reverse(original, original_id=row.id, reason=f"Removed from {run.number} during edit", actor_id=str(actor["user_id"]))

    for item_row in item_rows:
        if item_row.inventory_item_id:
            item = InventoryItem.query.filter_by(tenant_id=tenant_id, id=item_row.inventory_item_id).with_for_update().first()
            if item:
                item.consumed_qty = to_decimal(item.consumed_qty) - to_decimal(item_row.quantity)
                if item.consumed_run_id == run.id:
                    item.consumed_run_id = None
                    item.consumed_run_number = None
    # Not explicitly deleted here - deleting `consumption` below cascades to
    # these at the DB level (ondelete="CASCADE"); an explicit ORM delete on
    # both sides races with that cascade and can warn about a 0-row delete.

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="inventory.production.additional_component_removed", entity_type="production-run", entity_id=str(run.id), meta={"sku": consumption.sku, "quantity": decimal_str(consumption.quantity)})
    session.delete(consumption)
    session.commit()

    return _consumed_display(tenant_id, run.id)


# ============================================================================
# finished-good items (per-unit tracking for production output)
# ============================================================================


@router.get("/inventory/finished-goods")
def list_finished_good_items(
    actor: Actor = Depends(require_permission("inventory:read")),
    query: ListQuery = Depends(),
    status: str | None = None,
    available: bool | None = None,
    warehouseId: uuid_mod.UUID | None = None,
    productId: uuid_mod.UUID | None = None,
    productionRunId: uuid_mod.UUID | None = None,
    batchNo: str | None = None,
):
    tenant_id = actor["tenant_id"]

    q = FinishedGoodItem.query.filter(FinishedGoodItem.tenant_id == tenant_id)
    if status:
        q = q.filter(FinishedGoodItem.status == status)
    if available:
        q = q.filter(FinishedGoodItem.quantity - FinishedGoodItem.allocated_qty - FinishedGoodItem.shipped_qty > 0, FinishedGoodItem.status.in_(("available", "partially_reserved")))
    if warehouseId:
        assert_warehouse_in_scope(actor, warehouseId)
        q = q.filter(FinishedGoodItem.warehouse_id == warehouseId)
    else:
        q = scope_query_by_warehouse(q, FinishedGoodItem.warehouse_id, actor)
    if productId:
        q = q.filter(FinishedGoodItem.product_id == productId)
    if productionRunId:
        q = q.filter(FinishedGoodItem.production_run_id == productionRunId)
    if batchNo:
        q = q.filter(FinishedGoodItem.batch_no == batchNo)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(FinishedGoodItem.inventory_id.ilike(like), FinishedGoodItem.sku.ilike(like)))

    total = q.count()
    rows = q.order_by(FinishedGoodItem.inventory_id).limit(query.limit).offset(offset_of(query)).all()
    return list_response([_to_finished_good_item_api(r) for r in rows], query, total)


@router.get("/inventory/finished-goods/{id}")
def get_finished_good_item(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("inventory:read"))):
    tenant_id = actor["tenant_id"]
    item = _require_finished_good_item(tenant_id, id)
    assert_warehouse_in_scope(actor, item.warehouse_id)
    result = _to_finished_good_item_api(item)
    result["warehouseName"] = _warehouse_name(item.warehouse_id)
    run = ProductionRun.query.filter_by(tenant_id=tenant_id, id=item.production_run_id).first()
    result["productionRunNumber"] = run.number if run else None
    return result


@router.post("/inventory/finished-goods/{id}/transfer")
def transfer_finished_good_item(id: uuid_mod.UUID, body: FinishedGoodTransferBody, actor: Actor = Depends(require_permission("inventory:transfer"))):
    """Moves one whole FG unit to a new warehouse/location - a single-step,
    same-transaction move (available -> available directly), unlike the
    generic multi-line /inventory/transfers flow which stages through
    in_transit for a real shipment with its own lag. That distinction is
    deliberate: this is one already-produced physical unit changing bins,
    not a shipment in progress. Partial-quantity transfer of a lot-kind item
    isn't supported - the whole item moves."""
    tenant_id = actor["tenant_id"]
    item = _require_finished_good_item(tenant_id, id)
    assert_warehouse_in_scope(actor, item.warehouse_id)
    assert_warehouse_in_scope(actor, body.toWarehouseId)
    if to_decimal(item.allocated_qty) > 0:
        raise rule_violation(f"{item.inventory_id} is allocated to order {item.allocated_order_number} — remove the allocation before transferring it", code="FG_ITEM_ALLOCATED")
    if item.warehouse_id == body.toWarehouseId and item.location_id == body.toLocationId:
        raise rule_violation("Source and destination are the same", code="TRANSFER_INVALID")

    reference = _timestamp_ref("FGT")
    # reference_id stays the plain item id (not a compound key) so
    # GET /inventory/ledger?referenceId=<item.id> - the FG detail dialog's
    # movement-history query - finds both legs; movement_type already
    # differs between them (transfer_out vs transfer_in), so the idempotency
    # index doesn't need a distinguishing reference_id here.
    base = dict(tenant_id=tenant_id, product_id=item.product_id, sku=item.sku, batch_no=item.batch_no, uom=item.uom, bucket="available", reference_type="finished-good", reference_id=str(item.id), reference_no=reference, actor_id=str(actor["user_id"]), reason=body.reason)
    inventory_ledger.post(LedgerPosting(warehouse_id=item.warehouse_id, location_id=item.location_id, movement_type="transfer_out", quantity=decimal_str(-to_decimal(item.quantity)), **base))
    inventory_ledger.post(LedgerPosting(warehouse_id=body.toWarehouseId, location_id=body.toLocationId, movement_type="transfer_in", quantity=decimal_str(item.quantity), **base))

    from_warehouse = item.warehouse_id
    item.warehouse_id = body.toWarehouseId
    item.location_id = body.toLocationId
    item.location_code = None

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="inventory.finished_good.transferred", entity_type="finished-good-item", entity_id=str(item.id), meta={"inventoryId": item.inventory_id, "from": str(from_warehouse), "to": str(body.toWarehouseId)}, reason=body.reason)
    session.commit()
    return _to_finished_good_item_api(item)


@router.post("/inventory/finished-goods/{id}/status")
def change_finished_good_item_status(id: uuid_mod.UUID, body: FinishedGoodStatusBody, actor: Actor = Depends(require_permission("inventory:adjust"))):
    """Moves one FG unit between condition buckets (available/quarantine/
    damaged/expired) - the same bucket vocabulary StockBalance already uses
    everywhere else, posted as a status_change ledger pair scoped to this
    item specifically."""
    if body.toStatus not in ("available", "quarantine", "damaged", "expired"):
        raise rule_violation("toStatus must be one of available, quarantine, damaged, expired", code="STATUS_INVALID")
    tenant_id = actor["tenant_id"]
    item = _require_finished_good_item(tenant_id, id)
    assert_warehouse_in_scope(actor, item.warehouse_id)
    if to_decimal(item.allocated_qty) > 0:
        raise rule_violation(f"{item.inventory_id} is allocated to order {item.allocated_order_number} — remove the allocation before changing its status", code="FG_ITEM_ALLOCATED")
    if item.status == body.toStatus:
        raise rule_violation("Source and destination status are the same", code="STATUS_CHANGE_NOOP")

    reference = _timestamp_ref("FGS")
    # reference_id stays the plain item id (not a compound key) so
    # GET /inventory/ledger?referenceId=<item.id> - the FG detail dialog's
    # movement-history query - finds both legs; the out/in legs are told
    # apart via reference_type instead, since bucket is excluded from the
    # idempotency index and everything else here is identical between them.
    base = dict(tenant_id=tenant_id, product_id=item.product_id, sku=item.sku, warehouse_id=item.warehouse_id, location_id=item.location_id, batch_no=item.batch_no, uom=item.uom, movement_type="status_change", reference_id=str(item.id), reference_no=reference, actor_id=str(actor["user_id"]), reason=body.reason)
    inventory_ledger.post(LedgerPosting(reference_type=f"status:{item.status}->{body.toStatus}:out", quantity=decimal_str(-to_decimal(item.quantity)), bucket=item.status, **base))
    inventory_ledger.post(LedgerPosting(reference_type=f"status:{item.status}->{body.toStatus}:in", quantity=decimal_str(item.quantity), bucket=body.toStatus, **base))

    from_status = item.status
    item.status = body.toStatus
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="inventory.finished_good.status_changed", entity_type="finished-good-item", entity_id=str(item.id), meta={"inventoryId": item.inventory_id, "from": from_status, "to": body.toStatus}, reason=body.reason)
    session.commit()
    return _to_finished_good_item_api(item)


@router.post("/inventory/production/{id}/stages/{stage_key}/complete")
def complete_production_stage(id: uuid_mod.UUID, stage_key: str, body: StageCompleteBody, actor: Actor = Depends(require_permission("inventory:produce"))):
    """Marks one assembly stage done, stamped with who did it. Stages must be
    completed in sequence - a pack can't reach QC & PDI before its cells were
    ever tested."""
    if stage_key not in STAGE_KEYS:
        raise not_found("Production stage")
    tenant_id = actor["tenant_id"]

    run = ProductionRun.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not run:
        raise not_found("Production run")
    assert_warehouse_in_scope(actor, run.warehouse_id)

    stages = {s.stage_key: s for s in _run_stages(tenant_id, id)}
    stage = stages.get(stage_key)
    if not stage:
        raise not_found("Production stage")
    if stage.completed_at is not None:
        raise rule_violation(f"{STAGE_LABELS[stage_key]} is already marked done", code="STAGE_ALREADY_DONE")

    prior = [s for s in stages.values() if s.sequence < stage.sequence]
    unfinished_prior = [s for s in prior if s.completed_at is None]
    if unfinished_prior:
        blocking = sorted(unfinished_prior, key=lambda s: s.sequence)[0]
        raise rule_violation(f"{STAGE_LABELS[blocking.stage_key]} must be completed first", code="STAGE_OUT_OF_SEQUENCE")

    stage.associate_name = body.associateName
    stage.completed_at = datetime.now(timezone.utc)
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="inventory.production.stage_completed", entity_type="production-run", entity_id=str(id), meta={"stageKey": stage_key, "associateName": body.associateName})
    session.commit()

    return {"stages": [_to_stage_api(s) for s in _run_stages(tenant_id, id)]}
