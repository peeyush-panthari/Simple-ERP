"""Procurement > Purchase requisitions: an employee asks the Purchase department for something they need.

GET    /api/v1/purchase-requisitions                list (an employee sees their own; a reviewer sees everyone's submitted ones)
GET    /api/v1/purchase-requisitions/counts         how many are waiting for review / the caller's open ones
POST   /api/v1/purchase-requisitions                raise one (submit=false keeps it as a draft)
GET    /api/v1/purchase-requisitions/{id}
PATCH  /api/v1/purchase-requisitions/{id}           edit a draft or rejected requisition (its owner only)
POST   /api/v1/purchase-requisitions/{id}/submit    send a draft / rejected one on: to the requester's manager, or straight to Purchase when they have none
POST   /api/v1/purchase-requisitions/{id}/manager-approve   the requester's manager agrees; it moves on to Purchase
POST   /api/v1/purchase-requisitions/{id}/manager-reject    the manager declines, with a reason the requester sees
POST   /api/v1/purchase-requisitions/{id}/approve   Purchase agrees (never the person who raised it)
POST   /api/v1/purchase-requisitions/{id}/reject    Purchase declines, with a reason the requester sees
POST   /api/v1/purchase-requisitions/{id}/cancel    withdraw it (owner, or Purchase) with a reason once submitted
POST   /api/v1/purchase-requisitions/{id}/link-po   record the purchase order Purchase raised for an approved one

Permissions: pr:read + pr:write for employees (own requisitions only); pr:team_approve for managers (their direct reports'
requisitions); pr:approve for the Purchase department. Sourcing (RFQs) and purchase orders follow in domains/sourcing.
"""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_

from app.core.access_scope import assert_warehouse_in_scope
from app.core.audit import audit
from app.core.auth import Actor, require_any_permission, require_permission
from app.core.db import session
from app.core.errors import forbidden, not_found, rule_violation
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.money import to_decimal
from app.core.pagination import ListQuery, list_response, offset_of
from app.core.permissions import permits
from app.core.scalars import DecimalString, UomCode
from app.models.purchase_requisition import PurchaseRequisition, PurchaseRequisitionLine
from app.models.purchase_rfq import PurchaseRfq
from app.models.user import User
from app.services import procurement_repo, product_repo, requisition_repo, warehouse_repo
from app.services.po_approval import assert_not_self_approval
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1/purchase-requisitions", tags=["purchase-requisitions"])

_MIN_JUSTIFICATION = 3


class RequisitionLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    productId: uuid_mod.UUID | None = None
    itemName: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)
    quantity: DecimalString
    uom: UomCode | None = None


class RequisitionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    priority: str = "normal"
    department: str | None = Field(default=None, max_length=100)
    warehouseId: uuid_mod.UUID | None = None
    requiredBy: date | None = None
    justification: str | None = Field(default=None, max_length=2000)
    lines: list[RequisitionLineBody] = Field(min_length=1, max_length=100)
    submit: bool = False


class PatchRequisitionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    priority: str | None = None
    department: str | None = Field(default=None, max_length=100)
    warehouseId: uuid_mod.UUID | None = None
    requiredBy: date | None = None
    justification: str | None = Field(default=None, max_length=2000)
    lines: list[RequisitionLineBody] | None = Field(default=None, min_length=1, max_length=100)
    submit: bool = False


class NoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(default=None, max_length=1000)


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=1000)


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=1000)


class LinkPoBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purchaseOrderId: uuid_mod.UUID


def _is_reviewer(actor: Actor) -> bool:
    return permits(actor["permissions"], "pr:approve")


def _is_team_approver(actor: Actor) -> bool:
    return permits(actor["permissions"], "pr:team_approve")


def _actor_name(actor: Actor) -> str:
    return actor.get("name") or actor.get("email") or "Unknown user"


def _manager_of(req: PurchaseRequisition) -> User | None:
    """The requester's manager *now* - reassigning someone on Users & roles re-routes what is still waiting."""
    requester = User.query.filter_by(tenant_id=req.tenant_id, id=req.requester_id).first()
    if not requester or not requester.manager_id:
        return None
    return User.query.filter_by(tenant_id=req.tenant_id, id=requester.manager_id).first()


def _is_managed_by(actor: Actor, req: PurchaseRequisition) -> bool:
    if not _is_team_approver(actor):
        return False
    manager = _manager_of(req)
    return bool(manager and manager.id == actor["user_id"])


def _purchase_can_see(req: PurchaseRequisition) -> bool:
    """Purchase sees what has reached it - not drafts, not what is still with a manager, not what a manager turned down."""
    if req.status in ("draft", "pending_manager"):
        return False
    return not (req.status == "rejected" and req.rejected_stage == "manager")


def _visible(actor: Actor, req: PurchaseRequisition) -> bool:
    if req.requester_id == actor["user_id"]:
        return True
    if _is_reviewer(actor) and _purchase_can_see(req):
        return True
    return req.status != "draft" and _is_managed_by(actor, req)


def _require_visible(actor: Actor, req_id) -> PurchaseRequisition:
    req = requisition_repo.require(actor["tenant_id"], req_id)
    if not _visible(actor, req):
        raise not_found("Purchase requisition")
    return req


def _require_owner(actor: Actor, req: PurchaseRequisition, verb: str) -> None:
    if req.requester_id != actor["user_id"]:
        raise forbidden(f"{req.number} was raised by {req.requester_name}; only they can {verb} it", code="PR_NOT_OWNER")


def _clean_text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _validate(tenant_id, actor: Actor, *, priority: str, warehouse_id, required_by, lines: list[RequisitionLineBody], check_date: bool) -> dict:
    """Every problem is collected and reported together, like a purchase order's validation."""
    errors: list[dict] = []
    if priority not in requisition_repo.PRIORITIES:
        errors.append({"field": "priority", "message": f'"{priority}" is not a priority - use one of {", ".join(requisition_repo.PRIORITIES)}'})

    warehouse = None
    if warehouse_id:
        assert_warehouse_in_scope(actor, warehouse_id)
        warehouse = warehouse_repo.find_warehouse(tenant_id, warehouse_id)
        if not warehouse:
            errors.append({"field": "warehouseId", "message": f"Warehouse {warehouse_id} does not exist"})
        elif warehouse.status != "active":
            errors.append({"field": "warehouseId", "message": f"Warehouse {warehouse.code} is {warehouse.status}"})

    if check_date and required_by and required_by < date.today():
        errors.append({"field": "requiredBy", "message": f"Required-by date ({required_by.isoformat()}) is in the past"})

    products = product_repo.get_summaries(tenant_id, [l.productId for l in lines if l.productId])
    resolved = []
    for i, line in enumerate(lines):
        field = f"lines.{i}"
        if to_decimal(line.quantity) <= 0:
            errors.append({"field": f"{field}.quantity", "message": f"Line {i + 1}: quantity must be more than zero"})
        if line.productId:
            product = products.get(str(line.productId))
            if not product:
                errors.append({"field": field, "message": f"Line {i + 1}: product {line.productId} does not exist"})
                continue
            if not product["purchasable"]:
                errors.append({"field": field, "message": f"Line {i + 1}: {product['sku']} is not available to purchase (inactive or not flagged purchasable) - describe it as a new item instead"})
                continue
            resolved.append({"line": line, "product": product, "itemName": product["name"], "uom": line.uom or product["uom"]})
        else:
            name = _clean_text(line.itemName)
            if not name:
                errors.append({"field": f"{field}.itemName", "message": f"Line {i + 1}: pick a product or type what you need"})
                continue
            resolved.append({"line": line, "product": None, "itemName": name, "uom": line.uom or "UNIT"})

    if errors:
        raise rule_violation(
            f"The purchase requisition has {len(errors)} problem{'s' if len(errors) > 1 else ''}: {'; '.join(e['message'] for e in errors)}",
            code="PR_VALIDATION_FAILED",
            meta={"errors": errors},
        )
    return {"warehouse": warehouse, "lines": resolved}


def _insert_lines(tenant_id, req_id, resolved: list[dict]) -> None:
    for i, r in enumerate(resolved):
        session.add(
            PurchaseRequisitionLine(
                tenant_id=tenant_id,
                requisition_id=req_id,
                line_no=i + 1,
                product_id=r["product"]["id"] if r["product"] else None,
                sku=r["product"]["sku"] if r["product"] else None,
                item_name=r["itemName"],
                notes=_clean_text(r["line"].notes),
                quantity=r["line"].quantity,
                uom=r["uom"],
            )
        )


def _assert_ready_to_submit(req: PurchaseRequisition, line_count: int) -> None:
    if line_count < 1:
        raise rule_violation(f"{req.number} has no items - add at least one before sending it to Purchase", code="PR_NO_LINES")
    if len((req.justification or "").strip()) < _MIN_JUSTIFICATION:
        raise rule_violation(f"{req.number} needs a reason - say what the items are for so Purchase can decide", code="PR_JUSTIFICATION_REQUIRED")


def _submit_target(req: PurchaseRequisition) -> str:
    """Where a submitted requisition goes first: the requester's manager, or Purchase when there is none to ask."""
    manager = _manager_of(req)
    return "pending_manager" if manager and manager.status == "active" else "submitted"


def _mark_submitted(req: PurchaseRequisition) -> str:
    """Sends it on and clears every earlier decision - a rejected requisition starts the round again."""
    target = _submit_target(req)
    manager = _manager_of(req) if target == "pending_manager" else None
    req.status = target
    req.submitted_at = datetime.now(timezone.utc)
    req.manager_id = manager.id if manager else None
    req.manager_name = manager.display_name if manager else None
    req.manager_decided_at = None
    req.manager_note = None
    req.rejected_stage = None
    req.reviewed_by_id = None
    req.reviewed_by_name = None
    req.reviewed_at = None
    req.review_note = None
    return target


def _audit(actor: Actor, action: str, req: PurchaseRequisition, reason: str | None = None, **meta) -> None:
    audit(
        tenant_id=actor["tenant_id"], actor_id=actor["user_id"], actor_email=actor["email"], action=action, entity_type="purchase-requisition",
        entity_id=str(req.id), reason=reason, meta={"number": req.number, "status": req.status, **meta},
    )


def _detail(req: PurchaseRequisition) -> dict:
    out = requisition_repo.to_api(req, requisition_repo.lines_of(req.id))
    if req.status == "pending_manager":
        # Who it is waiting for, as of now.
        manager = _manager_of(req)
        out["managerName"] = manager.display_name if manager else req.manager_name
        out["managerId"] = str(manager.id) if manager else out["managerId"]
    rfq = PurchaseRfq.query.filter(PurchaseRfq.requisition_id == req.id, PurchaseRfq.status != "cancelled").order_by(PurchaseRfq.created_at.desc()).first()
    out["rfqId"] = str(rfq.id) if rfq else None
    out["rfqNumber"] = rfq.number if rfq else None
    out["rfqStatus"] = rfq.status if rfq else None
    return out


def _team_ids(actor: Actor):
    return session.query(User.id).filter(User.tenant_id == actor["tenant_id"], User.manager_id == actor["user_id"])


@router.get("")
def list_requisitions(
    actor: Actor = Depends(require_any_permission("pr:read", "pr:approve", "pr:team_approve")),
    query: ListQuery = Depends(),
    status: str | None = None,
    priority: str | None = None,
    mine: bool = False,
    team: bool = False,
):
    tenant_id = actor["tenant_id"]
    R = PurchaseRequisition
    q = R.query.filter(R.tenant_id == tenant_id)
    own = R.requester_id == actor["user_id"]
    team_vis = and_(R.status != "draft", R.requester_id.in_(_team_ids(actor))) if _is_team_approver(actor) else None
    purchase_vis = and_(R.status.notin_(("draft", "pending_manager")), R.rejected_stage.is_distinct_from("manager")) if _is_reviewer(actor) else None
    if mine:
        q = q.filter(own)
    elif team:
        # Just what the caller's own reports have raised.
        q = q.filter(team_vis) if team_vis is not None else q.filter(False)
    else:
        q = q.filter(or_(*[c for c in (own, team_vis, purchase_vis) if c is not None]))
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(R.status.in_(statuses))
    if priority:
        q = q.filter(R.priority == priority)
    if query.q:
        like = f"%{query.q}%"
        line_match = session.query(PurchaseRequisitionLine.requisition_id).filter(
            or_(PurchaseRequisitionLine.item_name.ilike(like), PurchaseRequisitionLine.sku.ilike(like))
        )
        q = q.filter(or_(R.number.ilike(like), R.requester_name.ilike(like), R.department.ilike(like), R.id.in_(line_match)))
    total = q.count()
    sortable = {"number": R.number, "created_at": R.created_at, "required_by": R.required_by, "status": R.status, "priority": R.priority}
    column = sortable.get((query.sort or "").lstrip("-"), R.created_at)
    order = column.desc() if (query.sort or "").startswith("-") or not query.sort else column.asc()
    rows = q.order_by(order, R.number.desc()).limit(query.limit).offset(offset_of(query)).all()
    summaries = requisition_repo.line_summaries([r.id for r in rows])
    return list_response([requisition_repo.to_api(r, summary=summaries.get(r.id, {"lineCount": 0, "itemsSummary": ""})) for r in rows], query, total)


@router.get("/counts")
def counts(actor: Actor = Depends(require_any_permission("pr:read", "pr:approve", "pr:team_approve"))):
    R = PurchaseRequisition
    tenant_id = actor["tenant_id"]
    mine = dict(
        session.query(R.status, func.count(R.id)).filter(R.tenant_id == tenant_id, R.requester_id == actor["user_id"]).group_by(R.status).all()
    )
    out = {"mine": {s: int(mine.get(s, 0)) for s in requisition_repo.STATUSES}, "awaitingReview": None, "awaitingMyApproval": None}
    if _is_reviewer(actor):
        out["awaitingReview"] = R.query.filter(R.tenant_id == tenant_id, R.status == "submitted").count()
    if _is_team_approver(actor):
        out["awaitingMyApproval"] = R.query.filter(R.tenant_id == tenant_id, R.status == "pending_manager", R.requester_id.in_(_team_ids(actor))).count()
    return out


@router.post("", status_code=201)
def create_requisition(body: RequisitionBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("pr:write"))):
    tenant_id = actor["tenant_id"]

    def _do():
        checked = _validate(tenant_id, actor, priority=body.priority, warehouse_id=body.warehouseId, required_by=body.requiredBy, lines=body.lines, check_date=True)
        number = next_document_number(tenant_id, "PR", pad=4, start=0)
        req = PurchaseRequisition(
            tenant_id=tenant_id,
            number=number,
            status="draft",
            priority=body.priority,
            requester_id=actor["user_id"],
            requester_name=_actor_name(actor),
            requester_email=actor["email"],
            department=_clean_text(body.department),
            warehouse_id=body.warehouseId,
            warehouse_code=checked["warehouse"].code if checked["warehouse"] else None,
            required_by=body.requiredBy,
            justification=_clean_text(body.justification),
        )
        session.add(req)
        session.flush()
        _insert_lines(tenant_id, req.id, checked["lines"])
        if body.submit:
            _assert_ready_to_submit(req, len(checked["lines"]))
            _mark_submitted(req)
        _audit(actor, "pr.created", req, lines=len(checked["lines"]), submitted=body.submit)
        session.commit()
        return 201, _detail(req)

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


@router.get("/{id}")
def get_requisition(id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission("pr:read", "pr:approve", "pr:team_approve"))):
    req = _require_visible(actor, id)
    result = _detail(req)
    result["canEdit"] = req.requester_id == actor["user_id"] and req.status in requisition_repo.EDITABLE
    return result


@router.patch("/{id}")
def patch_requisition(id: uuid_mod.UUID, body: PatchRequisitionBody, actor: Actor = Depends(require_permission("pr:write"))):
    tenant_id = actor["tenant_id"]
    req = _require_visible(actor, id)
    _require_owner(actor, req, "edit")
    if req.status not in requisition_repo.EDITABLE:
        raise rule_violation(f"{req.number} is {req.status} and can no longer be edited: only a draft or a rejected requisition can - ask Purchase, or start a new one", code="PR_NOT_EDITABLE")

    fields = body.model_fields_set
    priority = body.priority if "priority" in fields and body.priority else req.priority
    warehouse_id = body.warehouseId if "warehouseId" in fields else req.warehouse_id
    required_by = body.requiredBy if "requiredBy" in fields else req.required_by

    existing = requisition_repo.lines_of(req.id)
    if body.lines is not None:
        checked = _validate(tenant_id, actor, priority=priority, warehouse_id=warehouse_id, required_by=required_by, lines=body.lines, check_date="requiredBy" in fields)
        PurchaseRequisitionLine.query.filter_by(requisition_id=req.id).delete(synchronize_session=False)
        session.flush()
        _insert_lines(tenant_id, req.id, checked["lines"])
        line_count = len(checked["lines"])
        warehouse = checked["warehouse"]
    else:
        warehouse = _validate(tenant_id, actor, priority=priority, warehouse_id=warehouse_id, required_by=required_by, lines=[], check_date="requiredBy" in fields)["warehouse"]
        line_count = len(existing)

    req.priority = priority
    req.warehouse_id = warehouse_id
    req.warehouse_code = warehouse.code if warehouse else None
    req.required_by = required_by
    if "department" in fields:
        req.department = _clean_text(body.department)
    if "justification" in fields:
        req.justification = _clean_text(body.justification)
    if body.submit:
        requisition_repo.assert_transition(req, _submit_target(req), "submitted")
        _assert_ready_to_submit(req, line_count)
        _mark_submitted(req)
    _audit(actor, "pr.updated", req, lines=line_count, submitted=body.submit)
    session.commit()
    return _detail(req)


@router.post("/{id}/submit")
def submit_requisition(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("pr:write"))):
    req = _require_visible(actor, id)
    _require_owner(actor, req, "submit")
    requisition_repo.assert_transition(req, _submit_target(req), "submitted")
    _assert_ready_to_submit(req, len(requisition_repo.lines_of(req.id)))
    _mark_submitted(req)
    _audit(actor, "pr.submitted", req)
    session.commit()
    return _detail(req)


def _assert_manager_may_decide(actor: Actor, req: PurchaseRequisition) -> None:
    if req.status != "pending_manager":
        raise rule_violation(f"{req.number} is {req.status}, so it is not waiting for a manager's decision", code="PR_INVALID_STATE")
    if req.requester_id == actor["user_id"]:
        raise rule_violation(f"{req.number} was raised by you - your own manager has to decide on it", code="SELF_APPROVAL_BLOCKED")
    if not _is_managed_by(actor, req):
        manager = _manager_of(req)
        who = f"{manager.display_name} ({manager.email})" if manager else "nobody"
        raise forbidden(f"{req.number} is with {who}, the requester's manager - only they can approve or reject it", code="PR_NOT_MANAGER")


@router.post("/{id}/manager-approve")
def manager_approve(id: uuid_mod.UUID, body: NoteBody, actor: Actor = Depends(require_permission("pr:team_approve"))):
    req = _require_visible(actor, id)
    _assert_manager_may_decide(actor, req)
    req.status = "submitted"
    req.manager_id = actor["user_id"]
    req.manager_name = _actor_name(actor)
    req.manager_decided_at = datetime.now(timezone.utc)
    req.manager_note = _clean_text(body.note)
    _audit(actor, "pr.manager_approved", req, reason=req.manager_note)
    session.commit()
    return _detail(req)


@router.post("/{id}/manager-reject")
def manager_reject(id: uuid_mod.UUID, body: ReasonBody, actor: Actor = Depends(require_permission("pr:team_approve"))):
    req = _require_visible(actor, id)
    _assert_manager_may_decide(actor, req)
    req.status = "rejected"
    req.rejected_stage = "manager"
    req.manager_id = actor["user_id"]
    req.manager_name = _actor_name(actor)
    req.manager_decided_at = datetime.now(timezone.utc)
    req.manager_note = body.reason.strip()
    _audit(actor, "pr.manager_rejected", req, reason=req.manager_note)
    session.commit()
    return _detail(req)


@router.post("/{id}/approve")
def approve_requisition(id: uuid_mod.UUID, body: NoteBody, actor: Actor = Depends(require_permission("pr:approve"))):
    req = _require_visible(actor, id)
    requisition_repo.assert_transition(req, "approved", "approved")
    assert_not_self_approval(str(req.requester_id), str(actor["user_id"]), req.number)
    req.status = "approved"
    req.reviewed_by_id = actor["user_id"]
    req.reviewed_by_name = _actor_name(actor)
    req.reviewed_at = datetime.now(timezone.utc)
    req.review_note = _clean_text(body.note)
    _audit(actor, "pr.approved", req, reason=req.review_note)
    session.commit()
    return _detail(req)


@router.post("/{id}/reject")
def reject_requisition(id: uuid_mod.UUID, body: ReasonBody, actor: Actor = Depends(require_permission("pr:approve"))):
    req = _require_visible(actor, id)
    requisition_repo.assert_transition(req, "rejected", "rejected")
    assert_not_self_approval(str(req.requester_id), str(actor["user_id"]), req.number)
    req.status = "rejected"
    req.rejected_stage = "purchase"
    req.reviewed_by_id = actor["user_id"]
    req.reviewed_by_name = _actor_name(actor)
    req.reviewed_at = datetime.now(timezone.utc)
    req.review_note = body.reason.strip()
    _audit(actor, "pr.rejected", req, reason=req.review_note)
    session.commit()
    return _detail(req)


@router.post("/{id}/cancel")
def cancel_requisition(id: uuid_mod.UUID, body: CancelBody, actor: Actor = Depends(require_any_permission("pr:write", "pr:approve"))):
    req = _require_visible(actor, id)
    if req.requester_id != actor["user_id"] and not _is_reviewer(actor):
        raise forbidden(f"{req.number} was raised by {req.requester_name}; only they or Purchase can cancel it", code="PR_NOT_OWNER")
    requisition_repo.assert_transition(req, "cancelled", "cancelled")
    reason = _clean_text(body.reason)
    if req.status != "draft" and not reason:
        raise rule_violation(f"Say why {req.number} is being cancelled - the reason is kept with the requisition", code="PR_REASON_REQUIRED")
    was = req.status
    req.status = "cancelled"
    req.cancelled_reason = reason
    req.cancelled_at = datetime.now(timezone.utc)
    _audit(actor, "pr.cancelled", req, reason=reason, was=was)
    session.commit()
    return _detail(req)


@router.post("/{id}/link-po")
def link_purchase_order(id: uuid_mod.UUID, body: LinkPoBody, actor: Actor = Depends(require_permission("pr:approve", "po:read"))):
    tenant_id = actor["tenant_id"]
    req = _require_visible(actor, id)
    requisition_repo.assert_transition(req, "ordered", "marked as ordered")
    po = procurement_repo.find_po(tenant_id, body.purchaseOrderId)
    if not po:
        raise not_found("Purchase order")
    if po.status == "cancelled":
        raise rule_violation(f"{po.number} is cancelled - link the purchase order that actually covers {req.number}", code="PR_PO_CANCELLED")
    req.status = "ordered"
    req.purchase_order_id = po.id
    req.purchase_order_number = po.number
    _audit(actor, "pr.ordered", req, purchaseOrder=po.number)
    session.commit()
    return _detail(req)
