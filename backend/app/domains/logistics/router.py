"""Logistics: transport requests, RFQs/quotes/awards, dispatches + POD,
carrier invoices, and the public intake route. Ported 1:1 (behavior) from
backend_py/app/routes/logistics.py + logistics_public.py.

Carrier RFQ emails and the warehouse pre-dispatch email go through
notification_repo.send_notification (in-process, inline delivery - same as
the original); a failed send marks the invitation/dispatch "failed" rather
than raising. No cancel route exists for transport requests or RFQs - the
original has none either, despite `cancelled` existing in both state
machines.
"""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.access_scope import assert_warehouse_in_scope
from app.core.client_ip import client_ip
from app.core.audit import audit, read_audit_trail
from app.core.auth import Actor, require_permission
from app.core.config import settings
from app.core.db import session
from app.core.errors import ProblemError, conflict, not_found, rule_violation, too_many_requests
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.money import decimal_str, to_decimal
from app.core.pagination import ListQuery, list_response, offset_of
from app.core.scalars import DecimalString
from app.models.dispatch import Dispatch
from app.models.logistics_invoice import LogisticsInvoice
from app.models.public_request_throttle import PublicRequestThrottle
from app.models.quotation import Quotation
from app.models.rfq import Rfq
from app.models.rfq_invitation import RfqInvitation
from app.models.transport_request import TransportRequest
from app.services import finance_repo, logistics_repo, notification_repo, order_repo, party_summary, warehouse_repo
from app.services.logistics_rfq import (
    QuoteCandidate,
    assert_enough_invitations,
    assert_invoice_within_quotation,
    assert_quote_awardable,
    requires_award_justification,
)
from app.services.logistics_state import assert_transition
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1", tags=["logistics"])


class CreateRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customerId: uuid_mod.UUID | None = None
    customerName: str | None = Field(default=None, max_length=200)
    sourceWarehouseId: uuid_mod.UUID | None = None
    destLine1: str = Field(min_length=1, max_length=200)
    destCity: str = Field(min_length=1, max_length=100)
    destStateCode: str | None = Field(default=None, max_length=10)
    destPostalCode: str | None = Field(default=None, max_length=20)
    destCountry: str = "IN"
    goods: list[dict] = Field(default_factory=list)
    weightKg: DecimalString | None = None
    volumeM3: DecimalString | None = None
    packageCount: int | None = Field(default=None, ge=0)
    targetDate: date | None = None
    serviceLevel: str = "standard"
    insuranceRequired: bool = False
    insuredValue: DecimalString | None = None
    specialInstructions: str | None = Field(default=None, max_length=1000)


class RfqBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    carrierIds: list[uuid_mod.UUID] = Field(min_length=1, max_length=20)
    dueAt: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class QuoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    carrierId: uuid_mod.UUID
    amount: DecimalString
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    transitDays: int | None = Field(default=None, ge=0)
    validUntil: date | None = None
    serviceLevel: str | None = None
    inclusions: str | None = Field(default=None, max_length=500)


class AwardBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quotationId: uuid_mod.UUID
    justification: str | None = Field(default=None, max_length=500)


class DispatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transportRequestId: uuid_mod.UUID
    awbNumber: str | None = Field(default=None, max_length=60)
    vehicleNumber: str | None = Field(default=None, max_length=40)
    driverName: str | None = Field(default=None, max_length=120)
    driverPhone: str | None = Field(default=None, max_length=30)
    eta: date | None = None


class PodBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    podUrl: str = Field(max_length=1000)
    podDocumentId: str | None = Field(default=None, max_length=80)
    receivedBy: str = Field(min_length=2, max_length=120)
    deliveredAt: datetime | None = None


class LogisticsInvoiceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dispatchId: uuid_mod.UUID
    carrierInvoiceNumber: str = Field(min_length=1, max_length=60)
    amount: DecimalString
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    invoiceDate: date | None = None
    dueDate: date | None = None
    varianceApproved: bool = False
    varianceReason: str | None = Field(default=None, max_length=500)


def _quote_candidate(q: Quotation) -> QuoteCandidate:
    return QuoteCandidate(id=str(q.id), carrier_id=str(q.carrier_id), carrier_name=q.carrier_name, amount=decimal_str(q.amount), status=q.status, valid_until=q.valid_until.isoformat() if q.valid_until else None)


def _rfq_dict(r: Rfq) -> dict:
    return logistics_repo.to_rfq_api(
        r,
        invitations=[logistics_repo.to_invitation_api(i) for i in logistics_repo.invitations_of(r.id)],
        quotations=[logistics_repo.to_quotation_api(q) for q in logistics_repo.quotations_of(r.id)],
    )


def _request_detail(row: TransportRequest) -> dict:
    rfq_dicts = [_rfq_dict(r) for r in logistics_repo.rfqs_of(row.id)]
    dispatches = [logistics_repo.to_dispatch_api(d) for d in logistics_repo.dispatches_of(row.id)]
    return logistics_repo.to_request_api(row, rfqs=rfq_dicts, dispatches=dispatches)


@router.get("/transport-requests")
def list_requests(
    actor: Actor = Depends(require_permission("logistics:read")),
    query: ListQuery = Depends(),
    status: str | None = None,
    orderId: uuid_mod.UUID | None = None,
):
    tenant_id = actor["tenant_id"]

    q = TransportRequest.query.filter(TransportRequest.tenant_id == tenant_id)
    if actor["warehouse_ids"] is not None:
        # A request with no source warehouse isn't warehouse-specific and stays
        # visible to everyone with logistics:read; one that names a warehouse
        # is filtered to the actor's scope like everywhere else.
        q = q.filter(or_(TransportRequest.source_warehouse_id.is_(None), TransportRequest.source_warehouse_id.in_(actor["warehouse_ids"])))
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(TransportRequest.status.in_(statuses))
    if orderId:
        q = q.filter(TransportRequest.order_id == orderId)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(TransportRequest.number.ilike(like), TransportRequest.customer_name.ilike(like)))

    total = q.count()
    rows = q.order_by(TransportRequest.created_at.desc()).limit(query.limit).offset(offset_of(query)).all()

    # RFQs and their quotations for the whole page in two queries.
    rfqs_by_request: dict = {}
    quotes_by_rfq: dict = {}
    if rows:
        rfq_rows = logistics_repo.rfqs_for_requests([r.id for r in rows])
        for rfq in rfq_rows:
            rfqs_by_request.setdefault(rfq.transport_request_id, []).append(rfq)
        for q_row in logistics_repo.quotations_for_rfqs([rfq.id for rfq in rfq_rows]):
            quotes_by_rfq.setdefault(q_row.rfq_id, []).append(q_row)

    data = []
    for r in rows:
        rfqs = rfqs_by_request.get(r.id, [])
        best_quote = None
        awarded_carrier = None
        for rfq in rfqs:
            for q_row in quotes_by_rfq.get(rfq.id, []):
                if q_row.status in ("received", "approved"):
                    if best_quote is None or to_decimal(q_row.amount) < to_decimal(best_quote):
                        best_quote = decimal_str(q_row.amount)
                if q_row.status == "approved":
                    awarded_carrier = q_row.carrier_name
        data.append(logistics_repo.to_request_api(r, rfq_count=len(rfqs), best_quote=best_quote, awarded_carrier=awarded_carrier))
    return list_response(data, query, total)


@router.get("/transport-requests/{id}")
def get_request(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("logistics:read"))):
    row = logistics_repo.require_transport_request(actor["tenant_id"], id)
    if row.source_warehouse_id:
        assert_warehouse_in_scope(actor, row.source_warehouse_id)
    return _request_detail(row)


@router.post("/transport-requests", status_code=201)
def create_request(body: CreateRequestBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("logistics:write"))):
    tenant_id = actor["tenant_id"]
    if body.sourceWarehouseId:
        assert_warehouse_in_scope(actor, body.sourceWarehouseId)

    def _do():
        number = next_document_number(tenant_id, settings.lr_number_prefix, pad=4, start=2200)
        row = TransportRequest(
            tenant_id=tenant_id,
            number=number,
            source="manual",
            customer_id=body.customerId,
            customer_name=body.customerName,
            status="pending",
            source_warehouse_id=body.sourceWarehouseId,
            dest_line1=body.destLine1,
            dest_city=body.destCity,
            dest_state_code=body.destStateCode,
            dest_postal_code=body.destPostalCode,
            dest_country=body.destCountry,
            goods=body.goods,
            weight_kg=body.weightKg,
            volume_m3=body.volumeM3,
            package_count=body.packageCount,
            target_date=body.targetDate,
            service_level=body.serviceLevel,
            insurance_required=body.insuranceRequired,
            insured_value=body.insuredValue,
            special_instructions=body.specialInstructions,
            raised_by=str(actor["user_id"]),
        )
        session.add(row)
        session.flush()

        audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="logistics.request.created", entity_type="transport-request", entity_id=str(row.id), meta={"number": number})
        session.commit()
        return 201, logistics_repo.to_request_api(logistics_repo.require_transport_request(tenant_id, row.id))

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


@router.post("/transport-requests/{id}/rfq")
def publish_rfq(id: uuid_mod.UUID, body: RfqBody, actor: Actor = Depends(require_permission("logistics:write"))):
    tenant_id = actor["tenant_id"]
    row = logistics_repo.require_transport_request(tenant_id, id)
    if row.source_warehouse_id:
        assert_warehouse_in_scope(actor, row.source_warehouse_id)
    assert_transition(row.number, row.status, "rfq_sent")

    carriers = []
    missing = []
    for carrier_id in body.carrierIds:
        try:
            carrier = party_summary.build_summary_by_id(tenant_id, carrier_id)
        except ProblemError:
            carrier = None
        if not carrier:
            missing.append(str(carrier_id))
        else:
            carriers.append(carrier)
    if missing:
        raise not_found(f"Carrier {', '.join(missing)}")
    inactive = [c for c in carriers if c["status"] != "active"]
    if inactive:
        raise rule_violation(f"These carriers are not active: {', '.join(c['code'] for c in inactive)}", code="CARRIER_NOT_ACTIVE")

    number = next_document_number(tenant_id, settings.rfq_number_prefix, pad=4, start=1000)
    due_at = body.dueAt or (datetime.now(timezone.utc) + timedelta(hours=settings.rfq_response_hours))
    rfq = Rfq(tenant_id=tenant_id, number=number, transport_request_id=id, status="open", due_at=due_at, created_by=str(actor["user_id"]))
    session.add(rfq)
    session.flush()

    lane = f"{row.origin_city or row.source_warehouse_code or '?'} → {row.dest_city}"
    # A carrier needs a real street address to plan collection, not just the
    # origin city on the lane summary - pulled from the source warehouse's
    # own master data when it's linked.
    source_warehouse = warehouse_repo.get_warehouse_summary(tenant_id, row.source_warehouse_id) if row.source_warehouse_id else None
    pickup_address = (
        ", ".join(p for p in [source_warehouse.get("addressLine1"), source_warehouse.get("addressLine2"), source_warehouse.get("city"), source_warehouse.get("stateCode"), source_warehouse.get("postalCode")] if p)
        if source_warehouse
        else None
    )
    for carrier in carriers:
        if not carrier.get("email"):
            session.add(RfqInvitation(tenant_id=tenant_id, rfq_id=rfq.id, carrier_id=carrier["id"], carrier_name=carrier["displayName"], carrier_email=None, email_state="failed", email_error="No carrier email address on file"))
            continue
        try:
            result = notification_repo.send_notification(
                tenant_id,
                template="logistics.rfq",
                to=[carrier["email"]],
                data={
                    "rfqNumber": number,
                    "lane": lane,
                    "pickupAddress": pickup_address or "To be confirmed",
                    "targetDate": row.target_date.isoformat() if row.target_date else None,
                    "serviceLevel": row.service_level,
                    "dueAt": due_at.isoformat(),
                    "weightKg": decimal_str(row.weight_kg) if row.weight_kg is not None else None,
                },
                related_type="rfq",
                related_id=str(rfq.id),
            )
            email_state = notification_repo.delivery_state(result)
            email_error = result.get("error")
        except ProblemError as exc:
            email_state = "failed"
            email_error = exc.detail
        session.add(RfqInvitation(tenant_id=tenant_id, rfq_id=rfq.id, carrier_id=carrier["id"], carrier_name=carrier["displayName"], carrier_email=carrier.get("email"), email_state=email_state, email_error=email_error))

    row.status = "rfq_sent"
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="logistics.rfq.published", entity_type="transport-request", entity_id=str(id), meta={"rfqNumber": number, "carriers": len(carriers)})
    session.commit()

    return _request_detail(logistics_repo.require_transport_request(tenant_id, id))


@router.get("/rfqs")
def list_rfqs(actor: Actor = Depends(require_permission("logistics:read")), status: str | None = None, limit: int = 50):
    limit = min(limit, 200)
    q = Rfq.query.filter(Rfq.tenant_id == actor["tenant_id"])
    if status:
        q = q.filter(Rfq.status == status)
    rows = q.order_by(Rfq.created_at.desc()).limit(limit).all()
    return {"data": [_rfq_dict(r) for r in rows]}


@router.get("/dispatches")
def list_dispatches(actor: Actor = Depends(require_permission("logistics:read")), status: str | None = None, limit: int = 50):
    limit = min(limit, 200)
    q = Dispatch.query.filter(Dispatch.tenant_id == actor["tenant_id"])
    if status:
        q = q.filter(Dispatch.status == status)
    rows = q.order_by(Dispatch.dispatched_at.desc()).limit(limit).all()
    return {"data": [logistics_repo.to_dispatch_api(d) for d in rows]}


@router.post("/rfqs/{id}/quotes")
def record_quote(id: uuid_mod.UUID, body: QuoteBody, actor: Actor = Depends(require_permission("logistics:quote"))):
    tenant_id = actor["tenant_id"]
    rfq = Rfq.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not rfq:
        raise not_found("RFQ")
    if rfq.status != "open":
        raise conflict(f"{rfq.number} is {rfq.status} and no longer accepts quotations", code="RFQ_CLOSED")

    invitation = RfqInvitation.query.filter_by(rfq_id=id, carrier_id=body.carrierId).first()
    if not invitation:
        raise rule_violation("That carrier was not invited to this RFQ — invite them first, or record the quote against the right RFQ", code="CARRIER_NOT_INVITED")

    currency = body.currency or settings.base_currency
    existing = Quotation.query.filter_by(rfq_id=id, carrier_id=body.carrierId).first()
    if existing:
        existing.amount = body.amount
        existing.currency = currency
        existing.transit_days = body.transitDays
        existing.valid_until = body.validUntil
        existing.service_level = body.serviceLevel
        existing.inclusions = body.inclusions
        existing.status = "received"
        existing.recorded_by = str(actor["user_id"])
    else:
        session.add(
            Quotation(
                tenant_id=tenant_id,
                rfq_id=id,
                carrier_id=body.carrierId,
                carrier_name=invitation.carrier_name,
                amount=body.amount,
                currency=currency,
                transit_days=body.transitDays,
                valid_until=body.validUntil,
                service_level=body.serviceLevel,
                inclusions=body.inclusions,
                status="received",
                recorded_by=str(actor["user_id"]),
            )
        )

    request_row = logistics_repo.require_transport_request(tenant_id, rfq.transport_request_id)
    if request_row.status == "rfq_sent":
        request_row.status = "quotation_received"

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="logistics.quote.recorded", entity_type="rfq", entity_id=str(id), meta={"carrierId": str(body.carrierId), "amount": body.amount})
    session.commit()

    return _request_detail(logistics_repo.require_transport_request(tenant_id, rfq.transport_request_id))


@router.post("/rfqs/{id}/award")
def award_quote(id: uuid_mod.UUID, body: AwardBody, actor: Actor = Depends(require_permission("logistics:approve"))):
    tenant_id = actor["tenant_id"]
    rfq = Rfq.query.filter_by(tenant_id=tenant_id, id=id).first()
    if not rfq:
        raise not_found("RFQ")
    request_row_for_scope = logistics_repo.require_transport_request(tenant_id, rfq.transport_request_id)
    if request_row_for_scope.source_warehouse_id:
        assert_warehouse_in_scope(actor, request_row_for_scope.source_warehouse_id)
    if rfq.status != "open":
        raise conflict(f"{rfq.number} is already {rfq.status}", code="RFQ_CLOSED")

    invitations = logistics_repo.invitations_of(id)
    assert_enough_invitations(len(invitations), settings.rfq_min_invitations, rfq.number)

    quotations = logistics_repo.quotations_of(id)
    by_id = {str(q.id): q for q in quotations}
    chosen_row = by_id.get(str(body.quotationId))
    chosen = assert_quote_awardable(_quote_candidate(chosen_row) if chosen_row else None, rfq.number, date.today().isoformat())

    justification = requires_award_justification(chosen, [_quote_candidate(q) for q in quotations])
    if justification.required and not (body.justification or "").strip():
        raise rule_violation(
            f"{rfq.number}: the chosen quote is {justification.premium_percent}% above the cheapest ({justification.cheapest.carrier_name if justification.cheapest else '?'}) — a justification is required to award it",
            code="AWARD_JUSTIFICATION_REQUIRED",
            meta={"premiumPercent": justification.premium_percent},
        )

    for q in quotations:
        if str(q.id) == str(body.quotationId):
            q.status = "approved"
            q.approved_by = str(actor["user_id"])
            q.approved_at = datetime.now(timezone.utc)
        elif q.status == "received":
            q.status = "rejected"

    rfq.status = "awarded"
    rfq.awarded_quote_id = body.quotationId

    request_row = logistics_repo.require_transport_request(tenant_id, rfq.transport_request_id)
    request_row.status = "approved"

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="logistics.quote.awarded", entity_type="rfq", entity_id=str(id), reason=body.justification, meta={"quotationId": str(body.quotationId), "carrierId": chosen_row.carrier_id and str(chosen_row.carrier_id)})
    session.commit()

    return _request_detail(logistics_repo.require_transport_request(tenant_id, rfq.transport_request_id))


@router.post("/dispatches", status_code=201)
def create_dispatch(body: DispatchBody, actor: Actor = Depends(require_permission("logistics:dispatch"))):
    tenant_id = actor["tenant_id"]
    request_row = logistics_repo.require_transport_request(tenant_id, body.transportRequestId)
    if request_row.source_warehouse_id:
        assert_warehouse_in_scope(actor, request_row.source_warehouse_id)
    assert_transition(request_row.number, request_row.status, "dispatched")

    awarded_quote = None
    for rfq in logistics_repo.rfqs_of(request_row.id):
        for q in logistics_repo.quotations_of(rfq.id):
            if q.status == "approved":
                awarded_quote = q
                break
    if not awarded_quote:
        raise rule_violation(f"{request_row.number} has no approved quotation to dispatch against", code="DISPATCH_WITHOUT_APPROVED_QUOTATION")

    if request_row.order_id:
        pickable = logistics_repo.order_is_pickable(tenant_id, request_row.order_id)
        if not pickable["ready"]:
            raise rule_violation(pickable["reason"] or "The source order is not ready for dispatch", code="SOURCE_STOCK_NOT_READY")

    number = next_document_number(tenant_id, "DSP", pad=4, start=1000)
    dispatch = Dispatch(
        tenant_id=tenant_id,
        number=number,
        transport_request_id=request_row.id,
        quotation_id=awarded_quote.id,
        carrier_id=awarded_quote.carrier_id,
        carrier_name=awarded_quote.carrier_name,
        awb_number=body.awbNumber,
        vehicle_number=body.vehicleNumber,
        driver_name=body.driverName,
        driver_phone=body.driverPhone,
        status="dispatched",
        eta=body.eta,
        warehouse_notify_state="not_sent",
        created_by=str(actor["user_id"]),
    )
    session.add(dispatch)
    session.flush()

    warehouse = warehouse_repo.get_warehouse_summary(tenant_id, request_row.source_warehouse_id) if request_row.source_warehouse_id else None
    if warehouse and warehouse.get("contactEmail"):
        try:
            result = notification_repo.send_notification(
                tenant_id,
                template="logistics.pre-dispatch",
                to=[warehouse["contactEmail"]],
                data={"dispatchNumber": number, "requestNumber": request_row.number, "carrier": awarded_quote.carrier_name, "vehicleNumber": body.vehicleNumber, "eta": body.eta.isoformat() if body.eta else None},
                related_type="dispatch",
                related_id=str(dispatch.id),
            )
            dispatch.warehouse_notify_state = notification_repo.delivery_state(result, queued_state="not_sent")
        except ProblemError:
            dispatch.warehouse_notify_state = "failed"

    request_row.status = "dispatched"

    # Direct call in place of the original's DispatchCreated event - order's
    # logistics_state mirror happens synchronously, same transaction.
    if request_row.order_id:
        order_repo.mark_dispatched(tenant_id, request_row.order_id)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="logistics.dispatch.created", entity_type="dispatch", entity_id=str(dispatch.id), meta={"number": number, "carrier": awarded_quote.carrier_name})
    session.commit()

    return logistics_repo.to_dispatch_api(dispatch)


@router.post("/dispatches/{id}/pod")
def record_pod(id: uuid_mod.UUID, body: PodBody, actor: Actor = Depends(require_permission("logistics:dispatch"))):
    tenant_id = actor["tenant_id"]
    dispatch = session.query(Dispatch).filter_by(tenant_id=tenant_id, id=id).with_for_update().first()
    if not dispatch:
        raise not_found("Dispatch")
    if dispatch.status == "delivered":
        raise conflict(f"{dispatch.number} is already delivered", code="ALREADY_DELIVERED")

    dispatch.status = "delivered"
    dispatch.delivered_at = body.deliveredAt or datetime.now(timezone.utc)
    dispatch.pod_url = body.podUrl
    dispatch.pod_document_id = body.podDocumentId
    dispatch.pod_received_by = body.receivedBy

    request_row = logistics_repo.require_transport_request(tenant_id, dispatch.transport_request_id)
    request_row.status = "delivered"

    # Direct call in place of the original's DeliveryConfirmed event.
    if request_row.order_id:
        order_repo.mark_delivered(tenant_id, request_row.order_id, body.podUrl)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="logistics.dispatch.delivered", entity_type="dispatch", entity_id=str(id), meta={"number": dispatch.number, "podUrl": body.podUrl})
    session.commit()

    return logistics_repo.to_dispatch_api(dispatch)


@router.post("/logistics-invoices", status_code=201)
def create_logistics_invoice(body: LogisticsInvoiceBody, actor: Actor = Depends(require_permission("logistics:write"))):
    tenant_id = actor["tenant_id"]
    dispatch = session.query(Dispatch).filter_by(tenant_id=tenant_id, id=body.dispatchId).first()
    if not dispatch:
        raise not_found("Dispatch")

    quoted_amount = None
    if dispatch.quotation_id:
        quotation = Quotation.query.filter_by(id=dispatch.quotation_id).first()
        if quotation:
            quoted_amount = decimal_str(quotation.amount)

    number = next_document_number(tenant_id, "LINV", pad=4, start=1000)
    result = assert_invoice_within_quotation(invoice_number=body.carrierInvoiceNumber, amount=body.amount, quoted_amount=quoted_amount, variance_approved=body.varianceApproved, variance_reason=body.varianceReason)

    invoice = LogisticsInvoice(
        tenant_id=tenant_id,
        number=number,
        dispatch_id=dispatch.id,
        carrier_id=dispatch.carrier_id,
        carrier_name=dispatch.carrier_name,
        quotation_id=dispatch.quotation_id,
        amount=body.amount,
        currency=body.currency or settings.base_currency,
        invoice_date=body.invoiceDate or date.today(),
        due_date=body.dueDate or (date.today() + timedelta(days=30)),
        status="approved",
        variance_amount=result["variance"],
        variance_approved_by=str(actor["user_id"]) if body.varianceApproved else None,
        variance_reason=body.varianceReason,
        created_by=str(actor["user_id"]),
    )
    session.add(invoice)
    session.flush()

    # Finance's post_payable(), un-swallowed, in the same transaction, keyed
    # on this invoice's own freshly-generated LINV number (the stable dedup
    # key for AP's idempotent-on-vendor-invoice-no insert). LogisticsInvoice
    # .status never transitions past 'approved' after this succeeds.
    finance_repo.post_payable(tenant_id, source_type="logistics", source_id=str(invoice.id), reference=invoice.number, vendor_id=dispatch.carrier_id, vendor_name=dispatch.carrier_name, amount=invoice.amount, currency=invoice.currency, due_date=invoice.due_date, actor_user_id=str(actor["user_id"]))

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="logistics.invoice.recorded", entity_type="logistics-invoice", entity_id=str(invoice.id), meta={"number": number, "amount": body.amount, "variance": result["variance"]})
    session.commit()

    return {"id": str(invoice.id), "number": number, "amount": decimal_str(invoice.amount), "variance": result["variance"], "status": invoice.status}


@router.get("/logistics-invoices")
def list_logistics_invoices(actor: Actor = Depends(require_permission("logistics:read")), query: ListQuery = Depends()):
    q = LogisticsInvoice.query.filter(LogisticsInvoice.tenant_id == actor["tenant_id"])
    total = q.count()
    rows = q.order_by(LogisticsInvoice.created_at.desc()).limit(query.limit).offset(offset_of(query)).all()

    data = [
        {
            "id": str(r.id),
            "number": r.number,
            "dispatchId": str(r.dispatch_id),
            "carrierId": str(r.carrier_id),
            "carrierName": r.carrier_name,
            "amount": decimal_str(r.amount),
            "currency": r.currency,
            "invoiceDate": r.invoice_date.isoformat() if r.invoice_date else None,
            "dueDate": r.due_date.isoformat() if r.due_date else None,
            "status": r.status,
            "varianceAmount": decimal_str(r.variance_amount) if r.variance_amount is not None else None,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return list_response(data, query, total)


@router.get("/transport-requests/{id}/audit")
def request_audit(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("logistics:read"))):
    row = logistics_repo.require_transport_request(actor["tenant_id"], id)
    if row.source_warehouse_id:
        assert_warehouse_in_scope(actor, row.source_warehouse_id)
    rows = read_audit_trail(tenant_id=actor["tenant_id"], entity_type="transport-request", entity_id=str(id))
    return {
        "data": [
            {"id": str(r.id), "actor_id": str(r.actor_id) if r.actor_id else None, "actor_email": r.actor_email, "action": r.action, "reason": r.reason, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]
    }


# ============================================================================
# public intake (unauthenticated) - POST /public/transport-requests
# ============================================================================


class OriginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: str = Field(min_length=1, max_length=100)


class DestinationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line1: str = Field(min_length=3, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    stateCode: str | None = Field(default=None, max_length=10)
    postalCode: str | None = Field(default=None, max_length=20)
    country: str = "IN"


class PublicRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requesterName: str = Field(min_length=2, max_length=120)
    requesterEmail: str = Field(max_length=254)
    requesterPhone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=200)
    origin: OriginBody
    destination: DestinationBody
    goodsDescription: str = Field(min_length=3, max_length=1000)
    weightKg: DecimalString | None = None
    packageCount: int | None = Field(default=None, ge=1, le=10000)
    targetDate: date | None = None
    serviceLevel: str = "standard"
    insuranceRequired: bool = False
    # Honeypot: a real browser never fills this (hidden via CSS on the public
    # form); a bot that fills every field trips it. Accepted by the schema on
    # purpose - a validation error would tell the bot which field caught it.
    website: str | None = Field(default=None, max_length=500)


def _throttle_ip(ip: str) -> bool:
    """Fixed-hour-bucket upsert. Returns True if the request should be
    allowed (count, after incrementing, is still within the per-hour limit)."""
    now = datetime.now(timezone.utc)
    hour_bucket = now.replace(minute=0, second=0, microsecond=0)
    stmt = (
        pg_insert(PublicRequestThrottle)
        .values(scope="ip", identity=ip, hour_bucket=hour_bucket, count=1)
        .on_conflict_do_update(index_elements=["scope", "identity", "hour_bucket"], set_={"count": PublicRequestThrottle.count + 1})
        .returning(PublicRequestThrottle.count)
    )
    count = session.execute(stmt).scalar_one()
    return count <= settings.public_request_rate_per_hour


@router.post("/public/transport-requests", status_code=202)
def create_public_request(body: PublicRequestBody, request: Request):
    tenant_id = uuid_mod.UUID(settings.default_tenant_id)
    # The socket peer address, not X-Forwarded-For: with no trusted proxy in
    # front, that header is caller-controlled, so honouring it would let
    # anyone pick a fresh throttle identity per request.
    ip = client_ip(request) or "unknown"

    if body.website:
        # Honeypot tripped - fake success, nothing persisted.
        return {"status": "received"}

    if not _throttle_ip(ip):
        session.commit()
        raise too_many_requests("Too many requests from this address - try again later")
    session.commit()

    number = next_document_number(tenant_id, settings.lr_number_prefix, pad=4, start=2200)
    row = TransportRequest(
        tenant_id=tenant_id,
        number=number,
        source="external",
        customer_name=body.company or body.requesterName,
        status="pending",
        origin_city=body.origin.city,
        dest_line1=body.destination.line1,
        dest_city=body.destination.city,
        dest_state_code=body.destination.stateCode,
        dest_postal_code=body.destination.postalCode,
        dest_country=body.destination.country,
        goods=[{"description": body.goodsDescription}],
        weight_kg=body.weightKg,
        package_count=body.packageCount,
        target_date=body.targetDate,
        service_level=body.serviceLevel,
        insurance_required=body.insuranceRequired,
        special_instructions=f"Requested by {body.requesterName} ({body.requesterEmail})",
        raised_by="external",
        requester_email=body.requesterEmail,
        requester_ip=ip,
    )
    session.add(row)
    session.flush()

    audit(tenant_id=tenant_id, actor_id=None, actor_email=body.requesterEmail, action="logistics.request.external", entity_type="transport-request", entity_id=str(row.id), meta={"number": number, "requester": body.requesterEmail, "destination": body.destination.city})
    session.commit()

    # Anonymous callers only ever see a bare reference, never internal IDs.
    return {"status": "received", "reference": number}
