"""Transport-request/RFQ/dispatch queries + API projections - ported 1:1
from backend/services/logistics/src/routes/logistics.ts's repo-ish helpers.

Also hosts create_transport_request_from_order() - the direct-call
equivalent of POST /internal/transport-requests, called from order's
confirm-settlement/manual-logistics-override paths - and order_is_pickable()
- the direct-call equivalent of orderIsPickable(), the fail-closed
pick-readiness gate logistics checks before creating a dispatch.
"""

from __future__ import annotations

import uuid

from app.core.errors import not_found
from app.core.db import session
from app.models.dispatch import Dispatch
from app.models.quotation import Quotation
from app.models.rfq import Rfq
from app.models.rfq_invitation import RfqInvitation
from app.models.transport_request import TransportRequest
from app.services import warehouse_repo
from app.core.money import decimal_str
from app.services.sequences import next_document_number

_PICKABLE_STATUSES = ("allocated", "partially_allocated", "shipped", "partially_shipped", "invoiced", "fulfilled", "partially_fulfilled")


def find_transport_request(tenant_id: uuid.UUID, request_id: uuid.UUID) -> TransportRequest | None:
    return TransportRequest.query.filter_by(tenant_id=tenant_id, id=request_id).first()


def require_transport_request(tenant_id: uuid.UUID, request_id: uuid.UUID) -> TransportRequest:
    row = find_transport_request(tenant_id, request_id)
    if not row:
        raise not_found("Transport request")
    return row


def lock_transport_request(tenant_id: uuid.UUID, request_id: uuid.UUID) -> TransportRequest | None:
    return session.query(TransportRequest).filter_by(tenant_id=tenant_id, id=request_id).with_for_update().first()


def rfqs_of(request_id: uuid.UUID) -> list[Rfq]:
    return Rfq.query.filter_by(transport_request_id=request_id).order_by(Rfq.created_at.desc()).all()


def invitations_of(rfq_id: uuid.UUID) -> list[RfqInvitation]:
    return RfqInvitation.query.filter_by(rfq_id=rfq_id).all()


def quotations_of(rfq_id: uuid.UUID) -> list[Quotation]:
    return Quotation.query.filter_by(rfq_id=rfq_id).order_by(Quotation.amount).all()


def rfqs_for_requests(request_ids: list[uuid.UUID]) -> list[Rfq]:
    """Batched rfqs_of, for the transport-request list page."""
    if not request_ids:
        return []
    return Rfq.query.filter(Rfq.transport_request_id.in_(request_ids)).order_by(Rfq.created_at.desc()).all()


def quotations_for_rfqs(rfq_ids: list[uuid.UUID]) -> list[Quotation]:
    """Batched quotations_of, for the transport-request list page."""
    if not rfq_ids:
        return []
    return Quotation.query.filter(Quotation.rfq_id.in_(rfq_ids)).order_by(Quotation.amount).all()


def dispatches_of(request_id: uuid.UUID) -> list[Dispatch]:
    return Dispatch.query.filter_by(transport_request_id=request_id).order_by(Dispatch.dispatched_at.desc()).all()


# ---- API projections --------------------------------------------------------


def to_request_api(row: TransportRequest, *, rfqs: list[dict] | None = None, dispatches: list[dict] | None = None, rfq_count: int | None = None, best_quote: str | None = None, awarded_carrier: str | None = None) -> dict:
    result = {
        "id": str(row.id),
        "number": row.number,
        "source": row.source,
        "orderId": str(row.order_id) if row.order_id else None,
        "orderNumber": row.order_number,
        "customerId": str(row.customer_id) if row.customer_id else None,
        "customerName": row.customer_name,
        "status": row.status,
        "sourceWarehouseId": str(row.source_warehouse_id) if row.source_warehouse_id else None,
        "sourceWarehouseCode": row.source_warehouse_code,
        "originLine1": row.origin_line1,
        "originCity": row.origin_city,
        "originStateCode": row.origin_state_code,
        "originPostalCode": row.origin_postal_code,
        "originCountry": row.origin_country,
        "destLine1": row.dest_line1,
        "destCity": row.dest_city,
        "destStateCode": row.dest_state_code,
        "destPostalCode": row.dest_postal_code,
        "destCountry": row.dest_country,
        "lane": f"{row.origin_city or row.source_warehouse_code or '?'} → {row.dest_city}",
        "goods": row.goods,
        "weightKg": decimal_str(row.weight_kg) if row.weight_kg is not None else None,
        "volumeM3": decimal_str(row.volume_m3) if row.volume_m3 is not None else None,
        "packageCount": row.package_count,
        "targetDate": row.target_date.isoformat() if row.target_date else None,
        "serviceLevel": row.service_level,
        "insuranceRequired": row.insurance_required,
        "insuredValue": decimal_str(row.insured_value) if row.insured_value is not None else None,
        "specialInstructions": row.special_instructions,
        "trigger": row.trigger,
        "overrideReason": row.override_reason,
        "raisedBy": row.raised_by,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }
    if rfq_count is not None:
        result["rfqCount"] = rfq_count
    if best_quote is not None:
        result["bestQuote"] = best_quote
    if awarded_carrier is not None:
        result["awardedCarrier"] = awarded_carrier
    if rfqs is not None:
        result["rfqs"] = rfqs
    if dispatches is not None:
        result["dispatches"] = dispatches
    return result


def to_rfq_api(row: Rfq, *, invitations: list[dict] | None = None, quotations: list[dict] | None = None) -> dict:
    return {
        "id": str(row.id),
        "number": row.number,
        "transportRequestId": str(row.transport_request_id),
        "status": row.status,
        "dueAt": row.due_at.isoformat() if row.due_at else None,
        "awardedQuoteId": str(row.awarded_quote_id) if row.awarded_quote_id else None,
        "invitations": invitations if invitations is not None else [],
        "quotations": quotations if quotations is not None else [],
    }


def to_invitation_api(row: RfqInvitation) -> dict:
    return {"carrierId": str(row.carrier_id), "carrierName": row.carrier_name, "carrierEmail": row.carrier_email, "emailState": row.email_state, "emailError": row.email_error}


def to_quotation_api(row: Quotation) -> dict:
    return {
        "id": str(row.id),
        "carrierId": str(row.carrier_id),
        "carrierName": row.carrier_name,
        "amount": decimal_str(row.amount),
        "currency": row.currency,
        "transitDays": row.transit_days,
        "validUntil": row.valid_until.isoformat() if row.valid_until else None,
        "serviceLevel": row.service_level,
        "status": row.status,
    }


def to_dispatch_api(row: Dispatch) -> dict:
    return {
        "id": str(row.id),
        "number": row.number,
        "transportRequestId": str(row.transport_request_id),
        "quotationId": str(row.quotation_id) if row.quotation_id else None,
        "carrierId": str(row.carrier_id),
        "carrierName": row.carrier_name,
        "awbNumber": row.awb_number,
        "vehicleNumber": row.vehicle_number,
        "status": row.status,
        "dispatchedAt": row.dispatched_at.isoformat() if row.dispatched_at else None,
        "eta": row.eta.isoformat() if row.eta else None,
        "deliveredAt": row.delivered_at.isoformat() if row.delivered_at else None,
        "podUrl": row.pod_url,
        "podReceivedBy": row.pod_received_by,
    }


# ---- direct-call equivalent of POST /internal/transport-requests ------------


def create_transport_request_from_order(tenant_id: uuid.UUID, order, lines: list, *, trigger: str, raised_by: str | None, override_reason: str | None = None) -> TransportRequest:
    """Builds a `source='order'` transport request from the order's own
    delivery address, warehouse, and line items - the automatic-on-full-
    settlement / manual-override handoff point from order to logistics.

    Orders carry no warehouse of their own - by the time this fires the
    order has been allocated (this only runs from settlement/manual-override
    paths reachable once shipping is possible), so the source warehouse is
    derived from the lines' actual reservations, same as invoicing's GST
    place-of-supply lookup. If lines were allocated from different
    warehouses, this picks the earliest one - a shipment genuinely spanning
    multiple origins isn't modelled here."""
    from app.services import order_repo

    source_warehouse_id = order_repo.primary_reservation_warehouse_id(tenant_id, lines)
    source_warehouse = warehouse_repo.get_warehouse_summary(tenant_id, source_warehouse_id) if source_warehouse_id else None
    number = next_document_number(tenant_id, "LR", pad=4, start=2200)
    request = TransportRequest(
        tenant_id=tenant_id,
        number=number,
        source="order",
        order_id=order.id,
        order_number=order.number,
        customer_id=order.customer_id,
        customer_name=order.customer_name,
        status="pending",
        source_warehouse_id=source_warehouse_id,
        source_warehouse_code=source_warehouse["code"] if source_warehouse else None,
        dest_line1=order.delivery_line1 or "",
        dest_city=order.delivery_city or "",
        dest_state_code=order.delivery_state_code,
        dest_postal_code=order.delivery_postal_code,
        dest_country=order.delivery_country,
        goods=[{"sku": l.sku, "quantity": decimal_str(l.quantity), "uom": l.uom} for l in lines],
        target_date=order.promised_date,
        service_level="standard",
        trigger=trigger,
        override_reason=override_reason,
        raised_by=raised_by,
    )
    session.add(request)
    session.flush()
    return request


# ---- direct-call equivalent of orderIsPickable() -----------------------------


def order_is_pickable(tenant_id: uuid.UUID, order_id: uuid.UUID | None) -> dict:
    """Fail-closed: an order that can't be found or confirmed ready blocks
    the dispatch, same as Node's HTTP-failure branch."""
    from app.services import order_repo

    if not order_id:
        return {"ready": False, "reason": "This transport request has no linked order to check"}
    try:
        order = order_repo.get_summary(tenant_id, order_id)
    except Exception:
        order = None
    if not order:
        return {"ready": False, "reason": "Could not confirm with the order service whether stock is allocated"}
    if order["status"] not in _PICKABLE_STATUSES:
        return {"ready": False, "reason": f"{order['number']} is {order['status'].replace('_', ' ')} — stock has not been allocated yet"}
    return {"ready": True, "reason": None}
