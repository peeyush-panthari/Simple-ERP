"""Purchase requisitions: lookups, the status rules and the API shape.

  draft --submit--> pending_manager --manager approves--> submitted --Purchase approves--> approved --+--> sourcing (RFQ) --> ordered
    |                     |                                   |                                        \\--> ordered (direct PO)
    |                     \\--manager rejects--> rejected      \\--Purchase rejects--> rejected
    |                                                (edit and submit again: back to the manager)
    \\-- cancel (before it is ordered) --> cancelled

A requester with no manager on file skips the manager step. A requisition is a request, not a commitment: nothing here
touches stock, the ledgers or a vendor - sourcing and purchase orders do that.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from app.core.db import session
from app.core.errors import not_found, rule_violation
from app.core.money import decimal_str
from app.models.purchase_requisition import PurchaseRequisition, PurchaseRequisitionLine

PRIORITIES = ("low", "normal", "high", "urgent")
STATUSES = ("draft", "pending_manager", "submitted", "approved", "sourcing", "ordered", "rejected", "cancelled")

_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("pending_manager", "submitted", "cancelled"),
    "pending_manager": ("submitted", "rejected", "cancelled"),
    "submitted": ("approved", "rejected", "cancelled"),
    "approved": ("sourcing", "ordered", "cancelled"),
    "sourcing": ("approved", "ordered"),
    "rejected": ("pending_manager", "submitted", "cancelled"),
    "ordered": (),
    "cancelled": (),
}
EDITABLE = ("draft", "rejected")

_WAY_OUT = {
    "draft": "submit it first",
    "pending_manager": "it is waiting for the requester's manager",
    "submitted": "it is waiting for Purchase to review it",
    "approved": "it is already approved",
    "sourcing": "it is out for quotation - cancel the RFQ first, or finish it",
    "rejected": "edit it and submit it again",
    "ordered": "a purchase order already exists for it",
    "cancelled": "start a new requisition instead",
}


def assert_transition(req: PurchaseRequisition, to: str, verb: str) -> None:
    if to not in _TRANSITIONS.get(req.status, ()):
        raise rule_violation(f"{req.number} is {req.status}, so it cannot be {verb}: {_WAY_OUT.get(req.status, 'check its status')}", code="PR_INVALID_STATE")


def find(tenant_id: uuid.UUID, req_id: uuid.UUID) -> PurchaseRequisition | None:
    return PurchaseRequisition.query.filter_by(tenant_id=tenant_id, id=req_id).first()


def require(tenant_id: uuid.UUID, req_id: uuid.UUID) -> PurchaseRequisition:
    req = find(tenant_id, req_id)
    if not req:
        raise not_found("Purchase requisition")
    return req


def lines_of(req_id: uuid.UUID) -> list[PurchaseRequisitionLine]:
    return PurchaseRequisitionLine.query.filter_by(requisition_id=req_id).order_by(PurchaseRequisitionLine.line_no).all()


def line_to_api(l: PurchaseRequisitionLine) -> dict:
    return {
        "id": str(l.id),
        "lineNo": l.line_no,
        "productId": str(l.product_id) if l.product_id else None,
        "sku": l.sku,
        "itemName": l.item_name,
        "notes": l.notes,
        "quantity": decimal_str(l.quantity),
        "uom": l.uom,
        "inCatalogue": l.product_id is not None,
    }


def to_api(r: PurchaseRequisition, lines: list[PurchaseRequisitionLine] | None = None, *, summary: dict | None = None) -> dict:
    out = {
        "id": str(r.id),
        "number": r.number,
        "status": r.status,
        "priority": r.priority,
        "requesterId": str(r.requester_id),
        "requesterName": r.requester_name,
        "requesterEmail": r.requester_email,
        "department": r.department,
        "warehouseId": str(r.warehouse_id) if r.warehouse_id else None,
        "warehouseCode": r.warehouse_code,
        "requiredBy": r.required_by.isoformat() if r.required_by else None,
        "justification": r.justification,
        "managerId": str(r.manager_id) if r.manager_id else None,
        "managerName": r.manager_name,
        "managerDecidedAt": r.manager_decided_at.isoformat() if r.manager_decided_at else None,
        "managerNote": r.manager_note,
        "rejectedStage": r.rejected_stage,
        "submittedAt": r.submitted_at.isoformat() if r.submitted_at else None,
        "reviewedByName": r.reviewed_by_name,
        "reviewedAt": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "reviewNote": r.review_note,
        "purchaseOrderId": str(r.purchase_order_id) if r.purchase_order_id else None,
        "purchaseOrderNumber": r.purchase_order_number,
        "cancelledReason": r.cancelled_reason,
        "createdAt": r.created_at.isoformat() if r.created_at else None,
        "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
    }
    if lines is not None:
        out["lines"] = [line_to_api(l) for l in lines]
        out["lineCount"] = len(lines)
    if summary is not None:
        out.update(summary)
    return out


def line_summaries(req_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """"Item A, Item B +2 more" and the line count for a page of requisitions, in one query."""
    if not req_ids:
        return {}
    grouped: dict[uuid.UUID, list[str]] = defaultdict(list)
    rows = (
        session.query(PurchaseRequisitionLine.requisition_id, PurchaseRequisitionLine.item_name)
        .filter(PurchaseRequisitionLine.requisition_id.in_(req_ids))
        .order_by(PurchaseRequisitionLine.requisition_id, PurchaseRequisitionLine.line_no)
        .all()
    )
    for rid, name in rows:
        grouped[rid].append(name)
    out = {}
    for rid, names in grouped.items():
        extra = len(names) - 2
        out[rid] = {"lineCount": len(names), "itemsSummary": ", ".join(names[:2]) + (f" +{extra} more" if extra > 0 else "")}
    return out
