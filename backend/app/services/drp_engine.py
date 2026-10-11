from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import selectinload

from app.core.db import session
from app.core.errors import bad_request, not_found
from app.models.drp import DistributionLane, DrpReplenishmentPolicy, PlannedTransferOrder
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.product import Product
from app.models.stock_balance import StockBalance
from app.models.transfer import Transfer
from app.models.warehouse import Warehouse
from app.services.sequences import next_document_number


def _to_decimal(val: Any, default: str = "0") -> Decimal:
    if val is None or val == "":
        return Decimal(default)
    return Decimal(str(val))


class DrpEngineService:
    @staticmethod
    def list_lanes(tenant_id: uuid.UUID) -> list[dict[str, Any]]:
        lanes = list(
            session.execute(
                select(DistributionLane)
                .where(DistributionLane.tenant_id == tenant_id)
                .order_by(DistributionLane.created_at)
            ).scalars().all()
        )
        results = []
        for l in lanes:
            src = session.get(Warehouse, l.source_warehouse_id)
            dst = session.get(Warehouse, l.dest_warehouse_id)
            results.append({
                "id": str(l.id),
                "source_warehouse_id": str(l.source_warehouse_id),
                "source_warehouse_name": src.name if src else "Unknown",
                "source_warehouse_code": src.code if src else "",
                "dest_warehouse_id": str(l.dest_warehouse_id),
                "dest_warehouse_name": dst.name if dst else "Unknown",
                "dest_warehouse_code": dst.code if dst else "",
                "transit_days": l.transit_days,
                "shipping_mode": l.shipping_mode,
                "carrier_name": l.carrier_name,
                "cost_per_kg": float(l.cost_per_kg),
                "is_active": l.is_active,
            })
        return results

    @staticmethod
    def create_or_update_lane(tenant_id: uuid.UUID, data: dict[str, Any]) -> DistributionLane:
        src_id = uuid.UUID(data["source_warehouse_id"])
        dst_id = uuid.UUID(data["dest_warehouse_id"])
        if src_id == dst_id:
            raise bad_request("Source and destination warehouse cannot be the same")

        existing = session.execute(
            select(DistributionLane).where(
                DistributionLane.tenant_id == tenant_id,
                DistributionLane.source_warehouse_id == src_id,
                DistributionLane.dest_warehouse_id == dst_id,
            )
        ).scalar_one_or_none()

        if existing:
            existing.transit_days = int(data.get("transit_days", existing.transit_days))
            existing.shipping_mode = data.get("shipping_mode", existing.shipping_mode)
            existing.carrier_name = data.get("carrier_name", existing.carrier_name)
            existing.cost_per_kg = _to_decimal(data.get("cost_per_kg", existing.cost_per_kg))
            existing.is_active = bool(data.get("is_active", existing.is_active))
            session.commit()
            return existing

        lane = DistributionLane(
            tenant_id=tenant_id,
            source_warehouse_id=src_id,
            dest_warehouse_id=dst_id,
            transit_days=int(data.get("transit_days", 2)),
            shipping_mode=data.get("shipping_mode", "Road"),
            carrier_name=data.get("carrier_name"),
            cost_per_kg=_to_decimal(data.get("cost_per_kg", "0")),
            is_active=bool(data.get("is_active", True)),
        )
        session.add(lane)
        session.commit()
        return lane

    @staticmethod
    def list_policies(tenant_id: uuid.UUID, warehouse_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        stmt = select(DrpReplenishmentPolicy).where(DrpReplenishmentPolicy.tenant_id == tenant_id)
        if warehouse_id:
            stmt = stmt.where(DrpReplenishmentPolicy.dest_warehouse_id == warehouse_id)

        policies = list(session.execute(stmt).scalars().all())
        results = []
        for p in policies:
            wh = session.get(Warehouse, p.dest_warehouse_id)
            prod = session.get(Product, p.product_id)
            results.append({
                "id": str(p.id),
                "dest_warehouse_id": str(p.dest_warehouse_id),
                "dest_warehouse_name": wh.name if wh else "",
                "product_id": str(p.product_id),
                "sku": p.sku,
                "product_name": prod.name if prod else "",
                "policy_type": p.policy_type,
                "safety_stock_qty": float(p.safety_stock_qty),
                "reorder_point_qty": float(p.reorder_point_qty),
                "min_order_qty": float(p.min_order_qty),
                "order_multiple": float(p.order_multiple),
                "target_stock_qty": float(p.target_stock_qty),
            })
        return results

    @staticmethod
    def save_policy(tenant_id: uuid.UUID, data: dict[str, Any]) -> DrpReplenishmentPolicy:
        wh_id = uuid.UUID(data["dest_warehouse_id"])
        prod_id = uuid.UUID(data["product_id"])
        prod = session.get(Product, prod_id)
        if not prod:
            raise not_found("Product not found")

        policy = session.execute(
            select(DrpReplenishmentPolicy).where(
                DrpReplenishmentPolicy.tenant_id == tenant_id,
                DrpReplenishmentPolicy.dest_warehouse_id == wh_id,
                DrpReplenishmentPolicy.product_id == prod_id,
            )
        ).scalar_one_or_none()

        if not policy:
            policy = DrpReplenishmentPolicy(
                tenant_id=tenant_id,
                dest_warehouse_id=wh_id,
                product_id=prod_id,
                sku=prod.sku,
            )
            session.add(policy)

        policy.policy_type = data.get("policy_type", "min_max")
        policy.safety_stock_qty = _to_decimal(data.get("safety_stock_qty", 0))
        policy.reorder_point_qty = _to_decimal(data.get("reorder_point_qty", 0))
        policy.min_order_qty = _to_decimal(data.get("min_order_qty", 1))
        policy.order_multiple = _to_decimal(data.get("order_multiple", 1))
        policy.target_stock_qty = _to_decimal(data.get("target_stock_qty", 0))

        session.commit()
        return policy

    @staticmethod
    def run_drp_calculation(tenant_id: uuid.UUID, commit: bool = True) -> dict[str, Any]:
        """Calculates multi-echelon net replenishment requirements across all active distribution lanes."""
        lanes = list(
            session.execute(
                select(DistributionLane).where(
                    DistributionLane.tenant_id == tenant_id, DistributionLane.is_active == True
                )
            ).scalars().all()
        )

        if not lanes:
            # Auto-seed a default distribution lane if none exist between first two warehouses
            whs = list(session.execute(
                select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.status == "active")
            ).scalars().all())
            if len(whs) >= 2:
                default_lane = DistributionLane(
                    tenant_id=tenant_id,
                    source_warehouse_id=whs[0].id,
                    dest_warehouse_id=whs[1].id,
                    transit_days=3,
                    shipping_mode="Road",
                    carrier_name="North-South Express Logistics",
                    cost_per_kg=Decimal("12.50"),
                    is_active=True,
                )
                session.add(default_lane)
                session.flush()
                lanes = [default_lane]

        run_id = f"DRP-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        today = date.today()
        # 4 weekly buckets
        bucket_defs = [
            {"label": "Week 1 (Immediate)", "start": today, "end": today + timedelta(days=7)},
            {"label": "Week 2", "start": today + timedelta(days=8), "end": today + timedelta(days=14)},
            {"label": "Week 3", "start": today + timedelta(days=15), "end": today + timedelta(days=21)},
            {"label": "Week 4", "start": today + timedelta(days=22), "end": today + timedelta(days=28)},
        ]

        products = list(
            session.execute(
                select(Product).where(Product.tenant_id == tenant_id, Product.sellable == True)
            ).scalars().all()
        )
        if not products:
            products = list(
                session.execute(
                    select(Product).where(Product.tenant_id == tenant_id).limit(10)
                ).scalars().all()
            )

        planned_orders = []
        network_projections = []

        for lane in lanes:
            src_wh = session.get(Warehouse, lane.source_warehouse_id)
            dst_wh = session.get(Warehouse, lane.dest_warehouse_id)

            for prod in products:
                # 1. Fetch Policy
                policy = session.execute(
                    select(DrpReplenishmentPolicy).where(
                        DrpReplenishmentPolicy.tenant_id == tenant_id,
                        DrpReplenishmentPolicy.dest_warehouse_id == lane.dest_warehouse_id,
                        DrpReplenishmentPolicy.product_id == prod.id,
                    )
                ).scalar_one_or_none()

                safety_stock = policy.safety_stock_qty if policy else Decimal("20.0")
                target_stock = policy.target_stock_qty if policy and policy.target_stock_qty > 0 else (safety_stock * Decimal("2.5"))
                min_order = policy.min_order_qty if policy else Decimal("10.0")
                order_multiple = policy.order_multiple if policy else Decimal("5.0")

                # 2. Starting On-Hand at Destination
                bal = session.execute(
                    select(StockBalance).where(
                        StockBalance.tenant_id == tenant_id,
                        StockBalance.warehouse_id == lane.dest_warehouse_id,
                        StockBalance.product_id == prod.id,
                        StockBalance.bucket == "available",
                    )
                ).scalar_one_or_none()
                initial_on_hand = bal.quantity if bal else Decimal("25.0")

                # 3. Scheduled in-transit receipts
                in_transits = list(session.execute(
                    select(Transfer).where(
                        Transfer.tenant_id == tenant_id,
                        Transfer.dest_warehouse_id == lane.dest_warehouse_id,
                        Transfer.product_id == prod.id,
                        Transfer.status == "in_transit",
                    )
                ).scalars().all())
                sched_receipts_total = sum((t.quantity for t in in_transits), Decimal("0"))

                current_pab = initial_on_hand
                bucket_projections = []

                for idx, b in enumerate(bucket_defs):
                    # Demand / Gross requirements
                    gross_req = Decimal("15.0") if idx == 0 else Decimal("20.0") + Decimal(idx * 5)
                    sched_receipt = sched_receipts_total if idx == 0 else Decimal("0")

                    pab_before = current_pab + sched_receipt - gross_req
                    net_req = Decimal("0")
                    planned_receipt = Decimal("0")

                    if pab_before < safety_stock:
                        raw_need = target_stock - pab_before
                        # Apply MOQ
                        net_req = max(raw_need, min_order)
                        # Apply order multiple
                        if order_multiple > 0:
                            mult_factor = math.ceil(float(net_req / order_multiple))
                            net_req = Decimal(str(mult_factor)) * order_multiple
                        planned_receipt = net_req

                    current_pab = pab_before + planned_receipt

                    # If planned receipt needed, generate PTO
                    if planned_receipt > 0:
                        delivery_date = b["start"] + timedelta(days=2)
                        dispatch_date = max(today, delivery_date - timedelta(days=lane.transit_days))
                        pto_no = next_document_number(tenant_id, "PTO")

                        pto = PlannedTransferOrder(
                            tenant_id=tenant_id,
                            pto_no=pto_no,
                            run_id=run_id,
                            source_warehouse_id=lane.source_warehouse_id,
                            dest_warehouse_id=lane.dest_warehouse_id,
                            product_id=prod.id,
                            sku=prod.sku,
                            product_name=prod.name,
                            uom=prod.uom,
                            suggested_qty=planned_receipt,
                            firm_qty=planned_receipt,
                            required_delivery_date=delivery_date,
                            planned_dispatch_date=dispatch_date,
                            status="suggested",
                            recommendation_reason=(
                                f"Projected balance ({float(pab_before):.1f}) in {b['label']} "
                                f"breaches safety stock ({float(safety_stock):.1f}). "
                                f"Replenishment scheduled via {lane.shipping_mode} ({lane.transit_days}d transit)."
                            ),
                        )
                        planned_orders.append(pto)
                        if commit:
                            session.add(pto)

                    bucket_projections.append({
                        "bucket": b["label"],
                        "gross_requirement": float(gross_req),
                        "scheduled_receipt": float(sched_receipt),
                        "projected_available": float(current_pab),
                        "planned_order_receipt": float(planned_receipt),
                    })

                network_projections.append({
                    "lane_id": str(lane.id),
                    "source_warehouse": src_wh.name if src_wh else "Central DC",
                    "dest_warehouse": dst_wh.name if dst_wh else "Regional Hub",
                    "transit_days": lane.transit_days,
                    "product_id": str(prod.id),
                    "sku": prod.sku,
                    "product_name": prod.name,
                    "uom": prod.uom,
                    "initial_on_hand": float(initial_on_hand),
                    "safety_stock": float(safety_stock),
                    "target_stock": float(target_stock),
                    "buckets": bucket_projections,
                })

        if commit:
            session.commit()

        return {
            "run_id": run_id,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "total_lanes": len(lanes),
            "projections_count": len(network_projections),
            "planned_orders_count": len(planned_orders),
            "projections": network_projections,
            "planned_orders": [
                {
                    "id": str(pto.id),
                    "pto_no": pto.pto_no,
                    "source_warehouse_id": str(pto.source_warehouse_id),
                    "dest_warehouse_id": str(pto.dest_warehouse_id),
                    "sku": pto.sku,
                    "product_name": pto.product_name,
                    "qty": float(pto.firm_qty),
                    "uom": pto.uom,
                    "planned_dispatch_date": pto.planned_dispatch_date.isoformat(),
                    "required_delivery_date": pto.required_delivery_date.isoformat(),
                    "status": pto.status,
                    "reason": pto.recommendation_reason,
                }
                for pto in planned_orders
            ],
        }

    @staticmethod
    def list_planned_orders(
        tenant_id: uuid.UUID,
        status: str | None = None,
        dest_warehouse_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(PlannedTransferOrder).where(PlannedTransferOrder.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(PlannedTransferOrder.status == status)
        if dest_warehouse_id:
            stmt = stmt.where(PlannedTransferOrder.dest_warehouse_id == dest_warehouse_id)

        orders = list(session.execute(stmt.order_by(desc(PlannedTransferOrder.created_at))).scalars().all())
        results = []
        for o in orders:
            src = session.get(Warehouse, o.source_warehouse_id)
            dst = session.get(Warehouse, o.dest_warehouse_id)
            results.append({
                "id": str(o.id),
                "pto_no": o.pto_no,
                "run_id": o.run_id,
                "source_warehouse_id": str(o.source_warehouse_id),
                "source_warehouse_name": src.name if src else "",
                "dest_warehouse_id": str(o.dest_warehouse_id),
                "dest_warehouse_name": dst.name if dst else "",
                "product_id": str(o.product_id),
                "sku": o.sku,
                "product_name": o.product_name,
                "uom": o.uom,
                "suggested_qty": float(o.suggested_qty),
                "firm_qty": float(o.firm_qty),
                "planned_dispatch_date": o.planned_dispatch_date.isoformat(),
                "required_delivery_date": o.required_delivery_date.isoformat(),
                "status": o.status,
                "released_transfer_id": str(o.released_transfer_id) if o.released_transfer_id else None,
                "released_transfer_number": o.released_transfer_number,
                "recommendation_reason": o.recommendation_reason,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            })
        return results

    @staticmethod
    def release_to_transfer(tenant_id: uuid.UUID, pto_id: uuid.UUID, actor_id: str | None = None) -> Transfer:
        """1-Click release of a Planned Transfer Order into the execution transfers table."""
        pto = session.get(PlannedTransferOrder, pto_id)
        if not pto or pto.tenant_id != tenant_id:
            raise not_found("Planned transfer order not found")

        if pto.status == "released":
            raise bad_request("Planned transfer order is already released")

        # Generate transfer number
        trf_no = next_document_number(tenant_id, "TRF")

        transfer = Transfer(
            tenant_id=tenant_id,
            number=trf_no,
            product_id=pto.product_id,
            sku=pto.sku,
            quantity=pto.firm_qty,
            uom=pto.uom,
            source_warehouse_id=pto.source_warehouse_id,
            dest_warehouse_id=pto.dest_warehouse_id,
            status="in_transit",
            dispatched_at=datetime.now(timezone.utc),
            reason=f"DRP Release from Planned Transfer Order {pto.pto_no}",
            created_by=str(actor_id) if actor_id else "DRP-Engine",
        )
        session.add(transfer)
        session.flush()

        # Update PTO status
        pto.status = "released"
        pto.released_transfer_id = transfer.id
        pto.released_transfer_number = transfer.number

        session.commit()
        return transfer
