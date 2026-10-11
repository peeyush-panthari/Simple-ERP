"""Parties: CRUD, activate/block/unblock/deactivate, versions, audit, credit.
Ported 1:1 (behavior) from backend_py/app/routes/parties.py."""

from __future__ import annotations

import csv
import io
import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import or_

from app.core.auth import Actor, require_any_permission, require_permission
from app.core.audit import audit, read_audit_trail
from app.core.config import settings
from app.core.db import session
from app.core.errors import ProblemError, conflict, rule_violation
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.pagination import ListQuery, list_response, offset_of
from app.domains.parties.schemas import CreatePartyBody, PartyBulkUploadBody, PatchPartyBody, ReasonBody
from app.models.party import Party
from app.models.party_address import PartyAddress
from app.models.party_contact import PartyContact
from app.models.party_version import PartyVersion
from app.services import party_repo
from app.services.party_contactable import assert_no_header_injection
from app.services.party_credit import credit_position
from app.services.party_lifecycle import assert_activatable, assert_transition
from app.services.party_normalise import normalise_address, normalise_contact
from app.services.party_tax_id import assert_valid_tax_id
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1", tags=["parties"])

_SORTABLE = {
    "code": Party.code,
    "legal_name": Party.legal_name,
    "display_name": Party.display_name,
    "status": Party.status,
    "created_at": Party.created_at,
    "updated_at": Party.updated_at,
}

#  Orders (customer search), Procurement (vendor list) and GRN & QC all call
#  this list endpoint directly - not only the Party master module itself.
_PARTY_LOOKUP_PERMISSIONS = ("party:read", "order:read", "po:read", "warehouse:read", "sourcing:read")


@router.get("/parties")
def list_parties(
    actor: Actor = Depends(require_any_permission(*_PARTY_LOOKUP_PERMISSIONS)),
    query: ListQuery = Depends(),
    type: str | None = None,
    status: str | None = None,
    risk: str | None = None,
):
    q = Party.query.filter(Party.tenant_id == actor["tenant_id"])
    if type:
        q = q.filter(Party.type.in_([type, "both"]))
    if status:
        q = q.filter(Party.status == status)
    if risk:
        q = q.filter(Party.risk_flag == risk)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(
            or_(
                Party.code.ilike(like),
                Party.legal_name.ilike(like),
                Party.display_name.ilike(like),
                Party.tax_id.ilike(like),
            )
        )

    total = q.count()
    sort_col = _SORTABLE.get((query.sort or "").lstrip("-"), Party.display_name)
    order = sort_col.desc() if (query.sort or "").startswith("-") else sort_col.asc()
    rows = q.order_by(order).limit(query.limit).offset(offset_of(query)).all()

    return list_response([party_repo.to_party_api(r) for r in rows], query, total)


@router.get("/parties/{id}")
def get_party(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("party:read"))):
    return party_repo.to_aggregate_api(party_repo.load_aggregate(actor["tenant_id"], id))


def _create_party(tenant_id, actor: Actor, body: CreatePartyBody) -> Party:
    """Shared by the single-party create route and the bulk-upload route."""
    legal_name = assert_no_header_injection("legalName", body.legalName)
    tax = (
        assert_valid_tax_id(body.taxId, body.taxIdCountry or settings.party_home_country, validate=False)
        if body.taxId
        else None
    )

    name_owner = party_repo.find_by_legal_name(tenant_id, legal_name)
    if name_owner:
        raise conflict(f'A party named "{legal_name}" already exists ({name_owner.code})', code="LEGAL_NAME_TAKEN")

    if tax:
        owner = party_repo.find_tax_id_owner(tenant_id, tax.tax_id, tax.country)
        if owner:
            raise conflict(f"Tax ID {tax.tax_id} is already registered to {owner.display_name} ({owner.code})", code="TAX_ID_TAKEN")

    if not body.allowDuplicate:
        dupe = party_repo.find_duplicate(tenant_id, legal_name, tax.tax_id if tax else None)
        if dupe:
            raise conflict(
                f'"{legal_name}" already exists as {dupe.code} with the same tax ID. '
                "Edit that party, or resend with allowDuplicate=true if these are genuinely different entities",
                code="PARTY_DUPLICATE",
            )

    addresses = [
        normalise_address(
            type=a.type, label=a.label, line1=a.line1, line2=a.line2, city=a.city, state_code=a.stateCode, postal_code=a.postalCode,
            country=a.country, is_default=a.isDefault, path=f"addresses.{i}",
        )
        for i, a in enumerate(body.addresses)
    ]
    contacts = [
        normalise_contact(name=c.name, role=c.role, email=c.email, phone=c.phone, is_primary=c.isPrimary, path=f"contacts.{i}")
        for i, c in enumerate(body.contacts)
    ]

    code = body.code or next_document_number(tenant_id, settings.party_code_prefix, pad=4, start=100)

    party = Party(
        tenant_id=tenant_id,
        code=code,
        legal_name=legal_name,
        display_name=body.displayName or legal_name,
        type=body.type,
        subtype=body.subtype,
        tax_id=tax.tax_id if tax else None,
        tax_id_country=tax.country if tax else None,
        registration_no=body.registrationNo,
        payment_terms=body.paymentTerms,
        credit_limit=body.creditLimit,
        currency=body.currency or settings.base_currency,
        risk_flag=body.riskFlag,
        industry=body.industry,
        website=body.website,
        notes=body.notes,
    )
    session.add(party)
    session.flush()

    for a in addresses:
        session.add(
            PartyAddress(
                tenant_id=tenant_id,
                party_id=party.id,
                type=a.type,
                label=a.label,
                line1=a.line1,
                line2=a.line2,
                city=a.city,
                state_code=a.state_code,
                postal_code=a.postal_code,
                country=a.country,
                is_default=a.is_default,
            )
        )
    for c in contacts:
        session.add(
            PartyContact(
                tenant_id=tenant_id, party_id=party.id, name=c.name, role=c.role, email=c.email, phone=c.phone, is_primary=c.is_primary
            )
        )
    session.flush()

    party_repo.record_version(tenant_id=tenant_id, party_id=party.id, change_type="created", actor_id=actor["user_id"], actor_email=actor["email"])
    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="party.created",
        entity_type="party",
        entity_id=str(party.id),
    )
    session.commit()
    return party


@router.post("/parties", status_code=201)
def create_party(body: CreatePartyBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("party:write"))):
    tenant_id = actor["tenant_id"]

    def _do():
        party = _create_party(tenant_id, actor, body)
        return 201, party_repo.to_aggregate_api(party_repo.load_aggregate(tenant_id, party.id))

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


BULK_UPLOAD_REQUIRED_COLUMNS = ["legalName", "type"]


@router.post("/parties/bulk-upload")
def bulk_upload_parties(body: PartyBulkUploadBody, actor: Actor = Depends(require_permission("party:write"))):
    """Creates many parties from one CSV in a single request - one row per party."""
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    results = []
    for row_number, raw_row in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k}
        if not any(row.values()):
            continue
        label = row.get("legalName") or f"(row {row_number})"

        addresses = []
        if row.get("billingLine1"):
            addresses.append(
                {
                    "type": "billing",
                    "line1": row["billingLine1"],
                    "city": row.get("billingCity") or "",
                    "stateCode": row.get("billingStateCode") or None,
                    "postalCode": row.get("billingPostalCode") or None,
                    "country": "IN",
                    "isDefault": True,
                }
            )
        if row.get("shippingLine1"):
            addresses.append(
                {
                    "type": "shipping",
                    "label": row.get("shippingLocationName") or None,
                    "line1": row["shippingLine1"],
                    "city": row.get("shippingCity") or "",
                    "stateCode": row.get("shippingStateCode") or None,
                    "postalCode": row.get("shippingPostalCode") or None,
                    "country": "IN",
                    "isDefault": True,
                }
            )
        contacts = []
        if row.get("contactName"):
            contacts.append({"name": row["contactName"], "email": row.get("contactEmail") or None, "phone": row.get("contactPhone") or None, "isPrimary": True})

        try:
            create_body = CreatePartyBody(
                legalName=row.get("legalName") or "",
                type=row.get("type") or "",
                subtype=row.get("subtype") or None,
                taxId=row.get("taxId") or None,
                taxIdCountry=(row.get("taxIdCountry") or "IN") if row.get("taxId") else None,
                paymentTerms=row.get("paymentTerms") or None,
                currency=row.get("currency") or None,
                creditLimit=row.get("creditLimit") or "0",
                addresses=addresses,
                contacts=contacts,
            )
        except ValidationError as exc:
            results.append({"row": row_number, "legalName": label, "status": "error", "error": exc.errors()[0].get("msg", "invalid party data"), "rowData": row})
            continue

        try:
            party = _create_party(tenant_id, actor, create_body)
            results.append({"row": row_number, "legalName": label, "status": "success", "partyCode": party.code, "rowData": row})
        except ProblemError as exc:
            session.rollback()
            results.append({"row": row_number, "legalName": label, "status": "error", "error": exc.detail, "rowData": row})
        except Exception as exc:  # noqa: BLE001 - one bad row must not fail the whole batch
            session.rollback()
            results.append({"row": row_number, "legalName": label, "status": "error", "error": str(exc), "rowData": row})

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    return {
        "summary": {"totalRows": len(results), "successCount": success_count, "errorCount": error_count},
        "results": [
            {
                "row": r["row"],
                "legalName": r["legalName"],
                "status": r["status"],
                "partyCode": r.get("partyCode"),
                "error": r.get("error"),
                "rowData": r["rowData"] if r["status"] == "error" else {},
            }
            for r in results
        ],
    }


@router.patch("/parties/{id}")
def patch_party(id: uuid_mod.UUID, body: PatchPartyBody, actor: Actor = Depends(require_permission("party:write"))):
    tenant_id = actor["tenant_id"]
    before = party_repo.require_party(tenant_id, id)
    fields_set = body.model_fields_set

    if body.legalName is not None:
        name_owner = party_repo.find_by_legal_name(tenant_id, body.legalName, exclude_id=id)
        if name_owner:
            raise conflict(f'A party named "{body.legalName}" already exists ({name_owner.code})', code="LEGAL_NAME_TAKEN")

    tax = None
    if "taxId" in fields_set:
        if body.taxId is not None:
            tax = assert_valid_tax_id(body.taxId, body.taxIdCountry or before.tax_id_country or settings.party_home_country)

    if tax:
        owner = party_repo.find_tax_id_owner(tenant_id, tax.tax_id, tax.country, exclude_id=id)
        if owner:
            raise conflict(f"Tax ID {tax.tax_id} is already registered to {owner.display_name} ({owner.code})", code="TAX_ID_TAKEN")

    if "taxId" in fields_set and body.taxId is None and before.tax_id and before.status != "draft":
        raise rule_violation(f"{before.code} is already transactable — its tax ID cannot be removed, only corrected", code="TAX_ID_REQUIRED")

    if body.legalName is not None:
        before.legal_name = body.legalName
    if body.displayName is not None:
        before.display_name = body.displayName
    if body.type is not None:
        before.type = body.type
    if "subtype" in fields_set:
        before.subtype = body.subtype
    if "taxId" in fields_set:
        before.tax_id = tax.tax_id if tax else None
        before.tax_id_country = tax.country if tax else None
    if "registrationNo" in fields_set:
        before.registration_no = body.registrationNo
    if body.paymentTerms is not None:
        before.payment_terms = body.paymentTerms
    if body.creditLimit is not None:
        before.credit_limit = body.creditLimit
    if body.currency is not None:
        before.currency = body.currency
    if body.riskFlag is not None:
        before.risk_flag = body.riskFlag
    if "industry" in fields_set:
        before.industry = body.industry
    if "website" in fields_set:
        before.website = body.website
    if "notes" in fields_set:
        before.notes = body.notes

    party_repo.record_version(
        tenant_id=tenant_id, party_id=id, change_type="updated", reason=body.reason, actor_id=actor["user_id"], actor_email=actor["email"]
    )
    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="party.updated",
        entity_type="party",
        entity_id=str(id),
        reason=body.reason,
    )
    session.commit()

    return party_repo.to_aggregate_api(party_repo.load_aggregate(tenant_id, id))


@router.post("/parties/{id}/activate")
def activate_party(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("party:write"))):
    tenant_id = actor["tenant_id"]
    aggregate = party_repo.load_aggregate(tenant_id, id)
    assert_transition(aggregate.party.code, aggregate.party.status, "active")
    assert_activatable(
        code=aggregate.party.code,
        payment_terms=aggregate.party.payment_terms,
        currency=aggregate.party.currency,
        addresses=[{"type": a.type} for a in aggregate.addresses],
        contacts=[{"email": c.email} for c in aggregate.contacts],
    )

    aggregate.party.status = "active"
    aggregate.party.activated_at = datetime.now(timezone.utc)
    aggregate.party.blocked_reason = None
    aggregate.party.blocked_at = None

    party_repo.record_version(tenant_id=tenant_id, party_id=id, change_type="activated", actor_id=actor["user_id"], actor_email=actor["email"])
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="party.activated", entity_type="party", entity_id=str(id))
    session.commit()

    return party_repo.to_aggregate_api(party_repo.load_aggregate(tenant_id, id))


@router.post("/parties/{id}/block")
def block_party(id: uuid_mod.UUID, body: ReasonBody, actor: Actor = Depends(require_permission("party:block"))):
    tenant_id = actor["tenant_id"]
    party = party_repo.require_party(tenant_id, id)
    assert_transition(party.code, party.status, "blocked")

    party.status = "blocked"
    party.blocked_reason = body.reason
    party.blocked_at = datetime.now(timezone.utc)
    party.blocked_by = actor["user_id"]

    party_repo.record_version(
        tenant_id=tenant_id, party_id=id, change_type="blocked", reason=body.reason, actor_id=actor["user_id"], actor_email=actor["email"]
    )
    audit(
        tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="party.blocked", entity_type="party", entity_id=str(id), reason=body.reason
    )
    session.commit()

    return party_repo.to_aggregate_api(party_repo.load_aggregate(tenant_id, id))


@router.post("/parties/{id}/unblock")
def unblock_party(id: uuid_mod.UUID, body: ReasonBody, actor: Actor = Depends(require_permission("party:block"))):
    tenant_id = actor["tenant_id"]
    party = party_repo.require_party(tenant_id, id)
    assert_transition(party.code, party.status, "active")

    party.status = "active"
    party.blocked_reason = None
    party.blocked_at = None
    party.blocked_by = None

    party_repo.record_version(
        tenant_id=tenant_id, party_id=id, change_type="unblocked", reason=body.reason, actor_id=actor["user_id"], actor_email=actor["email"]
    )
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="party.unblocked", entity_type="party", entity_id=str(id), reason=body.reason)
    session.commit()

    return party_repo.to_aggregate_api(party_repo.load_aggregate(tenant_id, id))


@router.post("/parties/{id}/deactivate")
def deactivate_party(id: uuid_mod.UUID, body: ReasonBody, actor: Actor = Depends(require_permission("party:write"))):
    """Parties are never deleted — they go inactive so historical documents resolve."""
    tenant_id = actor["tenant_id"]
    party = party_repo.require_party(tenant_id, id)
    assert_transition(party.code, party.status, "inactive")

    party.status = "inactive"

    party_repo.record_version(
        tenant_id=tenant_id, party_id=id, change_type="deactivated", reason=body.reason, actor_id=actor["user_id"], actor_email=actor["email"]
    )
    audit(
        tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="party.deactivated", entity_type="party", entity_id=str(id), reason=body.reason
    )
    session.commit()

    return party_repo.to_aggregate_api(party_repo.load_aggregate(tenant_id, id))


@router.get("/parties/{id}/versions")
def party_versions(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("party:read"))):
    party_repo.require_party(actor["tenant_id"], id)
    rows = (
        PartyVersion.query.filter_by(tenant_id=actor["tenant_id"], party_id=id).order_by(PartyVersion.version.desc()).limit(200).all()
    )
    return {
        "data": [
            {
                "version": r.version,
                "changeType": r.change_type,
                "snapshot": r.snapshot,
                "reason": r.reason,
                "changedBy": r.changed_by,
                "changedByEmail": r.changed_by_email,
                "at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get("/parties/{id}/audit")
def party_audit(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("party:read"))):
    rows = read_audit_trail(tenant_id=actor["tenant_id"], entity_type="party", entity_id=str(id))
    return {
        "data": [
            {
                "id": str(r.id),
                "actor_id": str(r.actor_id) if r.actor_id else None,
                "actor_email": r.actor_email,
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "reason": r.reason,
                "correlation_id": r.correlation_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get("/parties/{id}/credit")
def party_credit(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("party:read"))):
    party = party_repo.require_party(actor["tenant_id"], id)
    position = credit_position(credit_limit=party.credit_limit, credit_used=party.credit_used, status=party.status)
    return {
        "partyId": str(id),
        "code": party.code,
        "currency": party.currency,
        "creditLimit": position.credit_limit,
        "creditUsed": position.credit_used,
        "creditAvailable": position.credit_available,
        "eligible": position.eligible,
        "reason": position.reason,
    }
