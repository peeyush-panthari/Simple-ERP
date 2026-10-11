from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import selectinload

from app.core.db import session
from app.core.errors import not_found
from app.models.business_entity import BusinessEntity
from app.models.party import Party
from app.models.party_address import PartyAddress
from app.models.product import Product
from app.models.bom import Bom
from app.models.bom_version import BomVersion
from app.models.bom_component import BomComponent
from app.models.warehouse import Warehouse
from app.models.subcontracting import (
    SubcontractOrder,
    SubcontractOrderLine,
    SubcontractChallan,
    SubcontractChallanItem,
    SubcontractReceipt,
)
from app.services.sequences import next_document_number


def _to_decimal(val: Any, default: str = "0") -> Decimal:
    if val is None or val == "":
        return Decimal(default)
    return Decimal(str(val))


class SubcontractingService:
    @staticmethod
    def list_orders(
        tenant_id: uuid.UUID,
        *,
        status: str | None = None,
        vendor_party_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(SubcontractOrder)
            .options(
                selectinload(SubcontractOrder.lines),
                selectinload(SubcontractOrder.challans),
                selectinload(SubcontractOrder.receipts),
            )
            .where(SubcontractOrder.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(SubcontractOrder.status == status)
        if vendor_party_id:
            stmt = stmt.where(SubcontractOrder.vendor_party_id == vendor_party_id)

        stmt = stmt.order_by(desc(SubcontractOrder.created_at)).limit(limit).offset(offset)
        orders = list(session.execute(stmt).scalars().all())

        results = []
        for o in orders:
            # Vendor name
            vendor = session.get(Party, o.vendor_party_id)
            vendor_name = vendor.legal_name if vendor else "Unknown Vendor"

            wh = session.get(Warehouse, o.source_warehouse_id)
            wh_name = wh.name if wh else "Unknown Warehouse"

            results.append({
                "id": str(o.id),
                "order_no": o.order_no,
                "vendor_party_id": str(o.vendor_party_id),
                "vendor_name": vendor_name,
                "source_warehouse_id": str(o.source_warehouse_id),
                "warehouse_name": wh_name,
                "fg_product_id": str(o.fg_product_id),
                "fg_sku": o.fg_sku,
                "fg_name": o.fg_name,
                "target_qty": float(o.target_qty),
                "received_qty": float(o.received_qty),
                "fulfillment_pct": round(float((o.received_qty / o.target_qty) * 100), 1) if o.target_qty > 0 else 0,
                "service_rate": float(o.service_rate),
                "service_sac_code": o.service_sac_code,
                "total_service_fee": float(o.target_qty * o.service_rate),
                "expected_delivery_date": o.expected_delivery_date.isoformat() if o.expected_delivery_date else None,
                "status": o.status,
                "challans_count": len(o.challans),
                "receipts_count": len(o.receipts),
                "created_at": o.created_at.isoformat() if o.created_at else None,
            })
        return results

    @staticmethod
    def create_order(tenant_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None) -> SubcontractOrder:
        vendor_id = uuid.UUID(data["vendor_party_id"])
        vendor = session.get(Party, vendor_id)
        if not vendor:
            raise not_found("Vendor party not found")

        fg_product_id = uuid.UUID(data["fg_product_id"])
        fg_prod = session.get(Product, fg_product_id)
        if not fg_prod:
            raise not_found("Finished good product not found")

        wh_id = uuid.UUID(data["source_warehouse_id"])
        wh = session.get(Warehouse, wh_id)
        if not wh:
            raise not_found("Source warehouse not found")

        # Business entity (Principal)
        entity_id = uuid.UUID(data["business_entity_id"]) if data.get("business_entity_id") else None
        if not entity_id:
            default_ent = session.execute(
                select(BusinessEntity).where(BusinessEntity.tenant_id == tenant_id, BusinessEntity.is_default == True)
            ).scalar_one_or_none()
            if default_ent:
                entity_id = default_ent.id

        order_no = next_document_number(tenant_id, "SCO")
        target_qty = _to_decimal(data.get("target_qty", "1"))
        service_rate = _to_decimal(data.get("service_rate", "0"))

        order = SubcontractOrder(
            tenant_id=tenant_id,
            order_no=order_no,
            vendor_party_id=vendor_id,
            business_entity_id=entity_id,
            source_warehouse_id=wh_id,
            fg_product_id=fg_product_id,
            fg_sku=fg_prod.sku,
            fg_name=fg_prod.name,
            bom_version_id=uuid.UUID(data["bom_version_id"]) if data.get("bom_version_id") else None,
            target_qty=target_qty,
            received_qty=Decimal("0"),
            service_rate=service_rate,
            service_sac_code=data.get("service_sac_code", "9988"),
            expected_delivery_date=datetime.strptime(data["expected_delivery_date"], "%Y-%m-%d").date()
            if data.get("expected_delivery_date")
            else None,
            status="confirmed",
            notes=data.get("notes"),
            created_by=actor_id,
        )
        session.add(order)
        session.flush()

        # Build raw material lines: from explicit lines or automatically from BOM
        lines_input = data.get("lines")
        if lines_input and len(lines_input) > 0:
            for l in lines_input:
                prod_id = uuid.UUID(l["product_id"])
                p = session.get(Product, prod_id)
                req_qty = _to_decimal(l.get("required_qty", "0"))
                line = SubcontractOrderLine(
                    tenant_id=tenant_id,
                    order_id=order.id,
                    product_id=prod_id,
                    sku=p.sku if p else l.get("sku", "UNKNOWN"),
                    name=p.name if p else l.get("name", "Raw Material"),
                    hsn_code=p.hsn_code if p and p.hsn_code else l.get("hsn_code", "7204"),
                    required_qty=req_qty,
                    dispatched_qty=Decimal("0"),
                    consumed_qty=Decimal("0"),
                    scrap_qty=Decimal("0"),
                    uom=p.uom if p else l.get("uom", "unit"),
                    estimated_unit_cost=_to_decimal(l.get("estimated_unit_cost", "100")),
                )
                session.add(line)
        else:
            # Auto-lookup BOM for this product
            bom = session.execute(
                select(Bom).where(Bom.tenant_id == tenant_id, Bom.product_id == fg_product_id, Bom.status == "active")
            ).scalar_one_or_none()
            if bom:
                # Find active version
                bom_ver = session.execute(
                    select(BomVersion).where(BomVersion.bom_id == bom.id, BomVersion.status == "active")
                ).scalar_one_or_none()
                if bom_ver:
                    comps = list(
                        session.execute(
                            select(BomComponent).where(BomComponent.bom_version_id == bom_ver.id)
                        ).scalars().all()
                    )
                    for c in comps:
                        p = session.get(Product, c.component_product_id)
                        comp_qty = c.quantity * target_qty
                        line = SubcontractOrderLine(
                            tenant_id=tenant_id,
                            order_id=order.id,
                            product_id=c.component_product_id,
                            sku=c.component_sku,
                            name=p.name if p else c.component_sku,
                            hsn_code=p.hsn_code if p and p.hsn_code else "7204",
                            required_qty=comp_qty,
                            dispatched_qty=Decimal("0"),
                            consumed_qty=Decimal("0"),
                            scrap_qty=Decimal("0"),
                            uom=c.uom,
                            estimated_unit_cost=Decimal("150.00"),
                        )
                        session.add(line)

        session.commit()
        return order

    @staticmethod
    def get_order_detail(tenant_id: uuid.UUID, order_id: uuid.UUID) -> dict[str, Any]:
        stmt = (
            select(SubcontractOrder)
            .options(
                selectinload(SubcontractOrder.lines),
                selectinload(SubcontractOrder.challans).selectinload(SubcontractChallan.items),
                selectinload(SubcontractOrder.receipts),
            )
            .where(SubcontractOrder.tenant_id == tenant_id, SubcontractOrder.id == order_id)
        )
        o = session.execute(stmt).scalar_one_or_none()
        if not o:
            raise not_found("Subcontract order not found")

        vendor = session.get(Party, o.vendor_party_id)
        wh = session.get(Warehouse, o.source_warehouse_id)
        ent = session.get(BusinessEntity, o.business_entity_id) if o.business_entity_id else None

        return {
            "id": str(o.id),
            "order_no": o.order_no,
            "vendor_party_id": str(o.vendor_party_id),
            "vendor_name": vendor.legal_name if vendor else "",
            "vendor_tax_id": vendor.tax_id if vendor else "URP",
            "principal_entity_name": ent.name if ent else "Principal Company",
            "principal_tax_id": ent.tax_id if ent else "",
            "source_warehouse_id": str(o.source_warehouse_id),
            "warehouse_name": wh.name if wh else "",
            "fg_product_id": str(o.fg_product_id),
            "fg_sku": o.fg_sku,
            "fg_name": o.fg_name,
            "target_qty": float(o.target_qty),
            "received_qty": float(o.received_qty),
            "balance_fg_qty": float(o.target_qty - o.received_qty),
            "service_rate": float(o.service_rate),
            "service_sac_code": o.service_sac_code,
            "expected_delivery_date": o.expected_delivery_date.isoformat() if o.expected_delivery_date else None,
            "status": o.status,
            "notes": o.notes,
            "lines": [
                {
                    "id": str(l.id),
                    "product_id": str(l.product_id),
                    "sku": l.sku,
                    "name": l.name,
                    "hsn_code": l.hsn_code,
                    "required_qty": float(l.required_qty),
                    "dispatched_qty": float(l.dispatched_qty),
                    "consumed_qty": float(l.consumed_qty),
                    "scrap_qty": float(l.scrap_qty),
                    "vendor_wip_balance": float(l.dispatched_qty - (l.consumed_qty + l.scrap_qty)),
                    "uom": l.uom,
                    "estimated_unit_cost": float(l.estimated_unit_cost),
                }
                for l in o.lines
            ],
            "challans": [
                {
                    "id": str(ch.id),
                    "challan_no": ch.challan_no,
                    "challan_date": ch.challan_date.isoformat(),
                    "statutory_due_date": ch.statutory_due_date.isoformat(),
                    "days_remaining_statutory": (ch.statutory_due_date - date.today()).days,
                    "transport_mode": ch.transport_mode,
                    "vehicle_no": ch.vehicle_no,
                    "eway_bill_no": ch.eway_bill_no,
                    "total_taxable_value": float(ch.total_taxable_value),
                    "total_challan_value": float(ch.total_challan_value),
                    "status": ch.status,
                    "items_count": len(ch.items),
                }
                for ch in o.challans
            ],
            "receipts": [
                {
                    "id": str(rc.id),
                    "receipt_no": rc.receipt_no,
                    "receipt_date": rc.receipt_date.isoformat(),
                    "received_qty": float(rc.received_qty),
                    "accepted_qty": float(rc.accepted_qty),
                    "rejected_qty": float(rc.rejected_qty),
                    "actual_scrap_qty": float(rc.actual_scrap_qty),
                    "allowable_scrap_qty": float(rc.allowable_scrap_qty),
                    "scrap_variance_qty": float(rc.scrap_variance_qty),
                    "scrap_variance_pct": float(rc.scrap_variance_pct),
                    "service_charges": float(rc.service_charges),
                    "vendor_challan_ref": rc.vendor_challan_ref,
                    "vendor_invoice_no": rc.vendor_invoice_no,
                    "qc_status": rc.qc_status,
                }
                for rc in o.receipts
            ],
        }

    @staticmethod
    def issue_delivery_challan(
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> SubcontractChallan:
        """Generates statutory Delivery Challan under CGST Section 143 & Rule 55."""
        order = session.get(SubcontractOrder, order_id)
        if not order or order.tenant_id != tenant_id:
            raise not_found("Subcontract order not found")

        # 1. Fetch Principal Entity details
        entity = None
        if order.business_entity_id:
            entity = session.get(BusinessEntity, order.business_entity_id)
        if not entity:
            entity = session.execute(
                select(BusinessEntity).where(BusinessEntity.tenant_id == tenant_id, BusinessEntity.is_default == True)
            ).scalar_one_or_none()

        consignor_name = entity.name if entity else "Principal Manufacturing Enterprise"
        consignor_gstin = entity.tax_id if (entity and entity.tax_id) else "27AAAAA0000A1Z5"
        consignor_address = (
            f"{entity.address_line1 or ''}, {entity.city or ''}, {entity.postal_code or ''}".strip(", ")
            if entity
            else "Plot 104, MIDC Industrial Area, Pune, Maharashtra 411018"
        )
        consignor_state = "Maharashtra"
        consignor_state_code = consignor_gstin[:2] if len(consignor_gstin) >= 2 and consignor_gstin[:2].isdigit() else "27"

        # 2. Fetch Job Worker (Vendor) Party details
        vendor = session.get(Party, order.vendor_party_id)
        vendor_addr = session.execute(
            select(PartyAddress).where(PartyAddress.party_id == order.vendor_party_id)
        ).scalar_one_or_none()

        consignee_name = vendor.legal_name if vendor else "Third Party Job Worker"
        consignee_gstin = vendor.tax_id if (vendor and vendor.tax_id) else "URP"
        consignee_address = (
            f"{vendor_addr.line1}, {vendor_addr.city}, {vendor_addr.postal_code or ''}".strip(", ")
            if vendor_addr
            else "Survey 45/2, Industrial Estate, Chakan, Pune 410501"
        )
        consignee_state = "Maharashtra"
        consignee_state_code = (
            consignee_gstin[:2] if len(consignee_gstin) >= 2 and consignee_gstin[:2].isdigit() else consignor_state_code
        )

        place_of_supply = data.get("place_of_supply", consignee_state)

        # 3. Consecutive Rule 55 serial number & 1-year statutory due date
        challan_no = next_document_number(tenant_id, "DC-JW")
        challan_date = datetime.now(timezone.utc)
        statutory_due_date = (challan_date + timedelta(days=365)).date()

        # 4. Tax logic: Intra-state (CGST + SGST) vs Inter-state (IGST)
        is_inter_state = consignor_state_code != consignee_state_code

        challan = SubcontractChallan(
            tenant_id=tenant_id,
            order_id=order.id,
            challan_no=challan_no,
            challan_date=challan_date,
            statutory_due_date=statutory_due_date,
            source_warehouse_id=order.source_warehouse_id,
            consignor_name=consignor_name,
            consignor_gstin=consignor_gstin,
            consignor_address=consignor_address,
            consignor_state=consignor_state,
            consignor_state_code=consignor_state_code,
            consignee_name=consignee_name,
            consignee_gstin=consignee_gstin,
            consignee_address=consignee_address,
            consignee_state=consignee_state,
            consignee_state_code=consignee_state_code,
            place_of_supply=place_of_supply,
            transport_mode=data.get("transport_mode", "Road"),
            vehicle_no=data.get("vehicle_no"),
            transporter_name=data.get("transporter_name"),
            eway_bill_no=data.get("eway_bill_no"),
            nature_of_processing=data.get("nature_of_processing", "Job-Work: Precision machining, coating & assembly"),
            statutory_declaration=(
                "Goods dispatched for job-work under Section 143 of CGST Act, 2017 read with Rule 55 "
                "of CGST Rules, 2017. Returnable within 1 year from the date of dispatch. "
                "Not an outward taxable supply/sale."
            ),
            total_taxable_value=Decimal("0"),
            total_cgst_amount=Decimal("0"),
            total_sgst_amount=Decimal("0"),
            total_igst_amount=Decimal("0"),
            total_challan_value=Decimal("0"),
            status="dispatched",
            notes=data.get("notes"),
            created_by=actor_id,
        )
        session.add(challan)
        session.flush()

        # 5. Populate Challan Items
        items_payload = data.get("items", [])
        total_taxable = Decimal("0")
        total_cgst = Decimal("0")
        total_sgst = Decimal("0")
        total_igst = Decimal("0")

        # Map order lines by product_id
        order_lines = list(session.execute(
            select(SubcontractOrderLine).where(SubcontractOrderLine.order_id == order.id)
        ).scalars().all())
        order_lines_by_pid = {l.product_id: l for l in order_lines}

        for idx, it in enumerate(items_payload, start=1):
            prod_id = uuid.UUID(it["product_id"])
            p = session.get(Product, prod_id)
            qty = _to_decimal(it["quantity"])
            rate = _to_decimal(it.get("taxable_rate", p.weight_kg if p and p.weight_kg else "120.00"))
            taxable_val = qty * rate
            gst_rate = _to_decimal(it.get("gst_rate_pct", "18.0"))

            if is_inter_state:
                cgst_rate = Decimal("0")
                sgst_rate = Decimal("0")
                igst_rate = gst_rate
                cgst_amt = Decimal("0")
                sgst_amt = Decimal("0")
                igst_amt = round((taxable_val * igst_rate) / Decimal("100"), 2)
            else:
                cgst_rate = gst_rate / Decimal("2")
                sgst_rate = gst_rate / Decimal("2")
                igst_rate = Decimal("0")
                cgst_amt = round((taxable_val * cgst_rate) / Decimal("100"), 2)
                sgst_amt = round((taxable_val * sgst_rate) / Decimal("100"), 2)
                igst_amt = Decimal("0")

            ch_item = SubcontractChallanItem(
                tenant_id=tenant_id,
                challan_id=challan.id,
                line_no=idx,
                product_id=prod_id,
                sku=p.sku if p else it.get("sku", "UNKNOWN"),
                description=p.name if p else it.get("description", "Material Item"),
                hsn_code=it.get("hsn_code") or (p.hsn_code if p and p.hsn_code else "7204"),
                quantity=qty,
                uom=it.get("uom") or (p.uom if p else "unit"),
                taxable_rate=rate,
                taxable_value=taxable_val,
                gst_rate_pct=gst_rate,
                cgst_rate=cgst_rate,
                cgst_amount=cgst_amt,
                sgst_rate=sgst_rate,
                sgst_amount=sgst_amt,
                igst_rate=igst_rate,
                igst_amount=igst_amt,
            )
            session.add(ch_item)

            total_taxable += taxable_val
            total_cgst += cgst_amt
            total_sgst += sgst_amt
            total_igst += igst_amt

            # Update dispatched qty on order line
            if prod_id in order_lines_by_pid:
                order_lines_by_pid[prod_id].dispatched_qty += qty

        challan.total_taxable_value = total_taxable
        challan.total_cgst_amount = total_cgst
        challan.total_sgst_amount = total_sgst
        challan.total_igst_amount = total_igst
        challan.total_challan_value = total_taxable + total_cgst + total_sgst + total_igst

        # Update order status
        order.status = "dispatched"
        session.commit()
        return challan

    @staticmethod
    def record_receipt(
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> SubcontractReceipt:
        """Records return of Finished Goods from Job Worker and calculates scrap variance."""
        order = session.get(SubcontractOrder, order_id)
        if not order or order.tenant_id != tenant_id:
            raise not_found("Subcontract order not found")

        received_qty = _to_decimal(data["received_qty"])
        accepted_qty = _to_decimal(data.get("accepted_qty", received_qty))
        rejected_qty = received_qty - accepted_qty

        # Scrap & Material Consumption
        actual_scrap_qty = _to_decimal(data.get("actual_scrap_qty", "0"))
        # Standard scrap tolerance is 5% or from BOM
        allowed_scrap_pct = _to_decimal(data.get("allowed_scrap_pct", "5.0"))
        consumed_rm = _to_decimal(data.get("consumed_raw_material_qty", accepted_qty))

        allowable_scrap_qty = (consumed_rm * allowed_scrap_pct) / Decimal("100")
        scrap_variance_qty = actual_scrap_qty - allowable_scrap_qty
        scrap_variance_pct = (
            round((scrap_variance_qty / consumed_rm) * Decimal("100"), 4) if consumed_rm > 0 else Decimal("0")
        )

        service_fee = accepted_qty * order.service_rate
        receipt_no = next_document_number(tenant_id, "SCR")

        receipt = SubcontractReceipt(
            tenant_id=tenant_id,
            order_id=order.id,
            receipt_no=receipt_no,
            receipt_date=datetime.now(timezone.utc),
            warehouse_id=order.source_warehouse_id,
            received_qty=received_qty,
            accepted_qty=accepted_qty,
            rejected_qty=rejected_qty,
            consumed_raw_material_qty=consumed_rm,
            actual_scrap_qty=actual_scrap_qty,
            allowable_scrap_qty=allowable_scrap_qty,
            scrap_variance_qty=scrap_variance_qty,
            scrap_variance_pct=scrap_variance_pct,
            vendor_challan_ref=data.get("vendor_challan_ref"),
            vendor_invoice_no=data.get("vendor_invoice_no"),
            service_charges=service_fee,
            qc_status=data.get("qc_status", "approved"),
            notes=data.get("notes"),
            created_by=actor_id,
        )
        session.add(receipt)

        # Update order received qty and status
        order.received_qty += accepted_qty
        if order.received_qty >= order.target_qty:
            order.status = "completed"
        else:
            order.status = "partially_received"

        # Update order lines consumed & scrap
        lines = list(session.execute(
            select(SubcontractOrderLine).where(SubcontractOrderLine.order_id == order.id)
        ).scalars().all())
        for l in lines:
            # Distribute consumption proportionally
            ratio = (accepted_qty / order.target_qty) if order.target_qty > 0 else Decimal("1")
            l.consumed_qty += l.required_qty * ratio
            l.scrap_qty += actual_scrap_qty

        session.commit()
        return receipt

    @staticmethod
    def get_statutory_challan(tenant_id: uuid.UUID, challan_id: uuid.UUID) -> dict[str, Any]:
        """Returns the full Rule 55 statutory Delivery Challan view."""
        stmt = (
            select(SubcontractChallan)
            .options(selectinload(SubcontractChallan.items))
            .where(SubcontractChallan.tenant_id == tenant_id, SubcontractChallan.id == challan_id)
        )
        ch = session.execute(stmt).scalar_one_or_none()
        if not ch:
            raise not_found("Delivery challan not found")

        order = session.get(SubcontractOrder, ch.order_id)

        return {
            "challan_id": str(ch.id),
            "challan_no": ch.challan_no,
            "challan_date": ch.challan_date.strftime("%d-%b-%Y"),
            "statutory_due_date": ch.statutory_due_date.strftime("%d-%b-%Y"),
            "statutory_law_ref": "CGST Section 143 read with Rule 55",
            "order_no": order.order_no if order else "",
            "fg_product": f"{order.fg_sku} - {order.fg_name}" if order else "",
            "consignor": {
                "name": ch.consignor_name,
                "gstin": ch.consignor_gstin,
                "address": ch.consignor_address,
                "state": ch.consignor_state,
                "state_code": ch.consignor_state_code,
            },
            "consignee": {
                "name": ch.consignee_name,
                "gstin": ch.consignee_gstin,
                "address": ch.consignee_address,
                "state": ch.consignee_state,
                "state_code": ch.consignee_state_code,
            },
            "place_of_supply": ch.place_of_supply,
            "transport": {
                "mode": ch.transport_mode,
                "vehicle_no": ch.vehicle_no or "N/A",
                "transporter": ch.transporter_name or "Direct Logistics",
                "eway_bill_no": ch.eway_bill_no or "Not Required (< ₹50k or exempted)",
            },
            "nature_of_processing": ch.nature_of_processing,
            "statutory_declaration": ch.statutory_declaration,
            "totals": {
                "taxable_value": float(ch.total_taxable_value),
                "cgst_amount": float(ch.total_cgst_amount),
                "sgst_amount": float(ch.total_sgst_amount),
                "igst_amount": float(ch.total_igst_amount),
                "total_challan_value": float(ch.total_challan_value),
            },
            "items": [
                {
                    "line_no": it.line_no,
                    "sku": it.sku,
                    "description": it.description,
                    "hsn_code": it.hsn_code,
                    "quantity": float(it.quantity),
                    "uom": it.uom,
                    "taxable_rate": float(it.taxable_rate),
                    "taxable_value": float(it.taxable_value),
                    "cgst_rate": float(it.cgst_rate),
                    "cgst_amount": float(it.cgst_amount),
                    "sgst_rate": float(it.sgst_rate),
                    "sgst_amount": float(it.sgst_amount),
                    "igst_rate": float(it.igst_rate),
                    "igst_amount": float(it.igst_amount),
                }
                for it in ch.items
            ],
        }
