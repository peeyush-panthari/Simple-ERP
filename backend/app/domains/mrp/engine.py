from __future__ import annotations

import math
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, or_, select

from app.core.db import session
from app.core.money import decimal_str, to_decimal
from app.services.bom_tree import TreeContext, build_explode_tree
from app.services.bom_explode import explode_bom
from app.models.bom import Bom
from app.models.bom_component import BomComponent
from app.models.bom_version import BomVersion
from app.models.mrp import MrpPlannedOrder, MrpRun
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.po_line import PoLine
from app.models.product import Product
from app.models.production_run import ProductionRun
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition, PurchaseRequisitionLine
from app.models.stock_balance import StockBalance
from app.models.warehouse import Warehouse
from app.services.sequences import next_document_number


def run_mrp_calculation(
    tenant_id: uuid.UUID,
    horizon_days: int = 30,
    warehouse_id: uuid.UUID | None = None,
    notes: str | None = None,
    actor_email: str | None = None,
) -> MrpRun:
    """Calculates gross and net requirements across sales orders, reorder points,

    existing stock, open purchase orders, and BOM explosion.
    """
    today = date.today()
    horizon_date = today + timedelta(days=horizon_days)

    # 1. Fetch relevant warehouses
    wh_query = select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.status == "active")
    if warehouse_id:
        wh_query = wh_query.where(Warehouse.id == warehouse_id)
    warehouses = session.execute(wh_query).scalars().all()
    if not warehouses:
        raise ValueError("No active warehouse found for MRP run")
    primary_wh = warehouses[0]

    # 2. Fetch all active products
    products = session.execute(
        select(Product).where(Product.tenant_id == tenant_id, Product.status == "active")
    ).scalars().all()
    product_map = {p.id: p for p in products}

    # 3. Available stock on hand per product
    # Projection from stock_balance (available bucket)
    sb_query = select(StockBalance).where(
        StockBalance.tenant_id == tenant_id,
        StockBalance.bucket == "available",
    )
    if warehouse_id:
        sb_query = sb_query.where(StockBalance.warehouse_id == warehouse_id)
    balances = session.execute(sb_query).scalars().all()

    on_hand_stock: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for b in balances:
        on_hand_stock[b.product_id] += to_decimal(b.quantity)

    # 4. Open purchase order supply (inbound)
    open_pos_query = (
        select(PoLine.product_id, PoLine.quantity, PoLine.received_qty)
        .join(PurchaseOrder, PoLine.po_id == PurchaseOrder.id)
        .where(
            PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.status.in_(["approved", "issued"]),
        )
    )
    if warehouse_id:
        open_pos_query = open_pos_query.where(PurchaseOrder.warehouse_id == warehouse_id)
    open_po_rows = session.execute(open_pos_query).all()

    inbound_po_supply: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for p_id, ordered, received in open_po_rows:
        open_qty = to_decimal(ordered) - to_decimal(received or 0)
        if open_qty > 0:
            inbound_po_supply[p_id] += open_qty

    # 5. Independent Demand: Unfulfilled Sales Orders within horizon
    so_lines_query = (
        select(OrderLine.product_id, OrderLine.quantity, OrderLine.shipped_qty, Order.promised_date, Order.number)
        .join(Order, OrderLine.order_id == Order.id)
        .where(
            Order.tenant_id == tenant_id,
            Order.status.in_(["confirmed", "allocated", "partially_allocated", "partially_shipped"]),
            Order.promised_date <= horizon_date,
        )
    )
    if warehouse_id:
        so_lines_query = so_lines_query.where(or_(Order.warehouse_id == warehouse_id, Order.warehouse_id.is_(None)))
    so_rows = session.execute(so_lines_query).all()

    gross_demand_items: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for p_id, ordered, shipped, promised_d, order_no in so_rows:
        unshipped = to_decimal(ordered) - to_decimal(shipped or 0)
        if unshipped > 0:
            gross_demand_items[p_id].append({
                "quantity": unshipped,
                "required_by": promised_d or (today + timedelta(days=7)),
                "source": order_no,
            })

    # 6. Reorder Point Demand
    for p in products:
        rop = to_decimal(p.reorder_point or 0)
        curr_avail = on_hand_stock[p.id] + inbound_po_supply[p.id]
        if rop > 0 and curr_avail < rop:
            shortfall = rop - curr_avail
            reorder_qty_val = to_decimal(p.reorder_qty) if p.reorder_qty else Decimal(0)
            if reorder_qty_val > 0:
                multiplier = math.ceil(shortfall / reorder_qty_val)
                reorder_need = reorder_qty_val * Decimal(multiplier)
            else:
                reorder_need = shortfall
                
            gross_demand_items[p.id].append({
                "quantity": reorder_need,
                "required_by": today + timedelta(days=p.lead_time_days or 3),
                "source": "REORDER_POINT",
            })

    # Create MrpRun record
    run_num = next_document_number(tenant_id, "MRP")
    mrp_run = MrpRun(
        tenant_id=tenant_id,
        number=run_num,
        horizon_days=horizon_days,
        warehouse_id=warehouse_id,
        warehouse_code=primary_wh.code if warehouse_id else "ALL",
        status="completed",
        notes=notes,
        created_by=actor_email,
    )
    session.add(mrp_run)
    session.flush()

    planned_orders: list[MrpPlannedOrder] = []

    # 7. First pass: Finished Goods / Manufactured Items
    component_extra_demand: dict[uuid.UUID, list[dict]] = defaultdict(list)

    for p in products:
        demands = gross_demand_items.get(p.id, [])
        if not demands:
            continue

        total_demand = sum(d["quantity"] for d in demands)
        pab = on_hand_stock[p.id] + inbound_po_supply[p.id]
        net_required = max(Decimal(0), total_demand - pab)

        if net_required <= 0:
            continue

        lead_days = p.lead_time_days or 3
        earliest_required = min(d["required_by"] for d in demands)
        suggested_order_date = max(today, earliest_required - timedelta(days=lead_days))
        source_summary = ", ".join(sorted(set(d["source"] for d in demands)))[:255]

        # Is this a manufactured finished good? Check if active approved BOM exists
        bom_row = session.execute(
            select(Bom)
            .where(Bom.tenant_id == tenant_id, Bom.product_id == p.id, Bom.status == "active")
        ).scalar_one_or_none()

        approved_version = None
        if bom_row:
            approved_version = session.execute(
                select(BomVersion)
                .where(BomVersion.bom_id == bom_row.id, BomVersion.state == "approved")
                .order_by(BomVersion.version.desc())
            ).scalars().first()

        if approved_version and (p.type == "finished_good" or not p.purchasable):
            # Planned Production Order
            plan_wo = MrpPlannedOrder(
                tenant_id=tenant_id,
                mrp_run_id=mrp_run.id,
                product_id=p.id,
                sku=p.sku,
                product_name=p.name,
                order_type="production",
                warehouse_id=primary_wh.id,
                warehouse_code=primary_wh.code,
                quantity=net_required,
                uom=p.uom,
                suggested_order_date=suggested_order_date,
                required_by_date=earliest_required,
                lead_time_days=lead_days,
                estimated_unit_cost=approved_version.cost_rollup,
                status="suggested",
                source_demand=source_summary,
            )
            session.add(plan_wo)
            planned_orders.append(plan_wo)

            # Explode BOM components down
            components = session.execute(
                select(BomComponent).where(BomComponent.bom_version_id == approved_version.id)
            ).scalars().all()

            ctx = TreeContext(tenant_id=tenant_id, as_of=today, max_depth=10)
            root_dict = {
                "product_id": str(p.id),
                "sku": p.sku,
                "uom": p.uom,
                "yield_percent": decimal_str(approved_version.yield_percent),
            }
            node = build_explode_tree(ctx, root_dict, components)
            explosion = explode_bom(node, decimal_str(net_required), max_depth=10)

            for req in explosion.requirements:
                component_extra_demand[uuid.UUID(req.product_id)].append({
                    "quantity": to_decimal(req.quantity),
                    "required_by": suggested_order_date,  # Needed when production starts
                    "source": f"BOM:{p.sku}",
                })
        else:
            # Planned Purchase Requisition (Purchasable finished goods or directly ordered items)
            if p.purchasable:
                plan_po = MrpPlannedOrder(
                    tenant_id=tenant_id,
                    mrp_run_id=mrp_run.id,
                    product_id=p.id,
                    sku=p.sku,
                    product_name=p.name,
                    order_type="purchase",
                    warehouse_id=primary_wh.id,
                    warehouse_code=primary_wh.code,
                    quantity=net_required,
                    uom=p.uom,
                    suggested_order_date=suggested_order_date,
                    required_by_date=earliest_required,
                    lead_time_days=lead_days,
                    estimated_unit_cost=None,
                    status="suggested",
                    source_demand=source_summary,
                )
                session.add(plan_po)
                planned_orders.append(plan_po)

    # 8. Second pass: Components exploded from BOMs
    for comp_prod_id, comp_demands in component_extra_demand.items():
        comp_prod = product_map.get(comp_prod_id)
        if not comp_prod:
            continue

        total_comp_demand = sum(cd["quantity"] for cd in comp_demands)
        pab = on_hand_stock[comp_prod.id] + inbound_po_supply[comp_prod.id]
        net_comp_required = max(Decimal(0), total_comp_demand - pab)

        if net_comp_required <= 0:
            continue

        lead_days = comp_prod.lead_time_days or 5
        earliest_required = min(cd["required_by"] for cd in comp_demands)
        suggested_order_date = max(today, earliest_required - timedelta(days=lead_days))
        source_summary = ", ".join(sorted(set(cd["source"] for cd in comp_demands)))[:255]

        # Check if component should respect reorder_qty
        reorder_qty_val = to_decimal(comp_prod.reorder_qty) if comp_prod.reorder_qty else Decimal(0)
        if reorder_qty_val > 0:
            multiplier = math.ceil(net_comp_required / reorder_qty_val)
            net_comp_required = reorder_qty_val * Decimal(multiplier)

        plan_comp_po = MrpPlannedOrder(
            tenant_id=tenant_id,
            mrp_run_id=mrp_run.id,
            product_id=comp_prod.id,
            sku=comp_prod.sku,
            product_name=comp_prod.name,
            order_type="purchase",
            warehouse_id=primary_wh.id,
            warehouse_code=primary_wh.code,
            quantity=net_comp_required,
            uom=comp_prod.uom,
            suggested_order_date=suggested_order_date,
            required_by_date=earliest_required,
            lead_time_days=lead_days,
            status="suggested",
            source_demand=source_summary,
        )
        session.add(plan_comp_po)
        planned_orders.append(plan_comp_po)

    mrp_run.total_skus_analyzed = len(products)
    mrp_run.planned_orders_count = len(planned_orders)
    session.commit()

    return mrp_run


def release_planned_orders(
    tenant_id: uuid.UUID,
    planned_order_ids: list[uuid.UUID],
    actor: dict,
) -> list[dict]:
    """Converts selected MrpPlannedOrders into real PurchaseRequisitions or ProductionRuns."""
    released_results = []
    actor_id = actor.get("sub") or actor.get("email") or "system"
    actor_name = actor.get("name") or actor.get("email") or "System Planner"

    orders = session.execute(
        select(MrpPlannedOrder).where(
            MrpPlannedOrder.tenant_id == tenant_id,
            MrpPlannedOrder.id.in_(planned_order_ids),
            MrpPlannedOrder.status == "suggested",
        )
    ).scalars().all()

    for po in orders:
        if po.order_type == "purchase":
            # Create a PurchaseRequisition + Line
            req_num = next_document_number(tenant_id, "PR")
            pr = PurchaseRequisition(
                tenant_id=tenant_id,
                number=req_num,
                status="approved",  # Pre-approved by MRP planner
                priority="normal",
                requester_id=uuid.UUID(actor.get("sub")) if actor.get("sub") else uuid.uuid4(),
                requester_name=actor_name,
                requester_email=actor.get("email"),
                department="Supply Chain Planning",
                warehouse_id=po.warehouse_id,
                warehouse_code=po.warehouse_code,
                required_by=po.required_by_date,
                justification=f"MRP Generated Planned Order from {po.source_demand}",
            )
            session.add(pr)
            session.flush()

            pr_line = PurchaseRequisitionLine(
                tenant_id=tenant_id,
                requisition_id=pr.id,
                line_no=1,
                product_id=po.product_id,
                sku=po.sku,
                item_name=po.product_name,
                quantity=po.quantity,
                uom=po.uom,
                notes=f"Needed by {po.required_by_date}",
            )
            session.add(pr_line)

            po.status = "released"
            po.released_reference_type = "purchase_requisition"
            po.released_reference_id = pr.id
            po.released_reference_number = pr.number
            po.released_at = date.today()
            po.released_by = actor_name

            released_results.append({
                "planned_order_id": po.id,
                "type": "purchase_requisition",
                "number": pr.number,
                "id": pr.id,
            })

        elif po.order_type == "production":
            # Create a ProductionRun in planned status
            run_num = next_document_number(tenant_id, "RUN")
            prod_run = ProductionRun(
                tenant_id=tenant_id,
                number=run_num,
                product_id=po.product_id,
                sku=po.sku,
                quantity=po.quantity,
                uom=po.uom,
                warehouse_id=po.warehouse_id,
                status="planned",
                production_date=po.required_by_date,
                notes=f"MRP Planned Order from {po.source_demand}",
                created_by=actor_name,
            )
            session.add(prod_run)
            session.flush()

            po.status = "released"
            po.released_reference_type = "production_run"
            po.released_reference_id = prod_run.id
            po.released_reference_number = prod_run.number
            po.released_at = date.today()
            po.released_by = actor_name

            released_results.append({
                "planned_order_id": po.id,
                "type": "production_run",
                "number": prod_run.number,
                "id": prod_run.id,
            })

    session.commit()
    return released_results
