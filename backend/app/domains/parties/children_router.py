"""POST/PATCH/DELETE addresses, contacts, bank accounts (+ approve/reject).
Ported 1:1 (behavior) from backend_py/app/routes/party_children.py."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response

from app.core.audit import audit
from app.core.auth import Actor, require_permission
from app.core.config import settings
from app.core.db import session
from app.core.errors import conflict, not_found, rule_violation
from app.domains.parties.schemas import AddressBody, ApproveBankAccountBody, BankAccountBody, ContactBody, RejectBankAccountBody
from app.models.party_address import PartyAddress
from app.models.party_bank_account import PartyBankAccount
from app.models.party_contact import PartyContact
from app.services import party_repo
from app.services.party_crypto import last_four, seal
from app.services.party_normalise import normalise_account_number, normalise_address, normalise_contact

router = APIRouter(prefix="/api/v1", tags=["party-children"])


def _normalised_address(body: AddressBody):
    return normalise_address(
        type=body.type, label=body.label, line1=body.line1, line2=body.line2, city=body.city, state_code=body.stateCode,
        postal_code=body.postalCode, country=body.country, is_default=body.isDefault,
    )


# ---- addresses --------------------------------------------------------------


@router.post("/parties/{id}/addresses", status_code=201)
def add_address(id: uuid_mod.UUID, body: AddressBody, actor: Actor = Depends(require_permission("party:write"))):
    tenant_id = actor["tenant_id"]
    party_repo.require_party(tenant_id, id)
    address = _normalised_address(body)

    if address.is_default:
        PartyAddress.query.filter_by(party_id=id, type=address.type).update({"is_default": False})

    row = PartyAddress(
        tenant_id=tenant_id, party_id=id, type=address.type, label=address.label, line1=address.line1, line2=address.line2, city=address.city,
        state_code=address.state_code, postal_code=address.postal_code, country=address.country, is_default=address.is_default,
    )
    session.add(row)
    session.flush()

    party_repo.record_version(tenant_id=tenant_id, party_id=id, change_type="address.added", actor_id=actor["user_id"], actor_email=actor["email"])
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="party.address.added", entity_type="party", entity_id=str(id))
    session.commit()
    return party_repo.to_address_api(row)


@router.patch("/parties/{id}/addresses/{childId}")
def update_address(id: uuid_mod.UUID, childId: uuid_mod.UUID, body: AddressBody, actor: Actor = Depends(require_permission("party:write"))):
    tenant_id = actor["tenant_id"]
    party_repo.require_party(tenant_id, id)
    address = _normalised_address(body)

    if address.is_default:
        PartyAddress.query.filter(PartyAddress.party_id == id, PartyAddress.type == address.type, PartyAddress.id != childId).update({"is_default": False})

    row = PartyAddress.query.filter_by(tenant_id=tenant_id, party_id=id, id=childId).first()
    if not row:
        raise not_found("Address")
    row.type = address.type
    row.label = address.label
    row.line1 = address.line1
    row.line2 = address.line2
    row.city = address.city
    row.state_code = address.state_code
    row.postal_code = address.postal_code
    row.country = address.country
    row.is_default = address.is_default

    party_repo.record_version(tenant_id=tenant_id, party_id=id, change_type="address.updated", actor_id=actor["user_id"], actor_email=actor["email"])
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="party.address.updated", entity_type="party", entity_id=str(id))
    session.commit()
    return party_repo.to_address_api(row)


@router.delete("/parties/{id}/addresses/{childId}", status_code=204)
def delete_address(id: uuid_mod.UUID, childId: uuid_mod.UUID, actor: Actor = Depends(require_permission("party:write"))):
    tenant_id = actor["tenant_id"]
    aggregate = party_repo.load_aggregate(tenant_id, id)
    target = next((a for a in aggregate.addresses if a.id == childId), None)
    if not target:
        raise not_found("Address")

    if aggregate.party.status == "active" and target.type == "billing" and sum(1 for a in aggregate.addresses if a.type == "billing") == 1:
        raise rule_violation(f"{aggregate.party.code} is active — removing its only billing address would break invoicing", code="BILLING_ADDRESS_REQUIRED")

    session.delete(target)
    party_repo.record_version(tenant_id=tenant_id, party_id=id, change_type="address.removed", actor_id=actor["user_id"], actor_email=actor["email"])
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="party.address.removed", entity_type="party", entity_id=str(id))
    session.commit()
    return Response(status_code=204)


# ---- contacts -----------------------------------------------------------


@router.post("/parties/{id}/contacts", status_code=201)
def add_contact(id: uuid_mod.UUID, body: ContactBody, actor: Actor = Depends(require_permission("party:write"))):
    tenant_id = actor["tenant_id"]
    party_repo.require_party(tenant_id, id)

    contact = normalise_contact(name=body.name, role=body.role, email=body.email, phone=body.phone, is_primary=body.isPrimary)

    if contact.is_primary:
        PartyContact.query.filter_by(party_id=id).update({"is_primary": False})

    row = PartyContact(tenant_id=tenant_id, party_id=id, name=contact.name, role=contact.role, email=contact.email, phone=contact.phone, is_primary=contact.is_primary)
    session.add(row)
    session.flush()

    party_repo.record_version(tenant_id=tenant_id, party_id=id, change_type="contact.added", actor_id=actor["user_id"], actor_email=actor["email"])
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="party.contact.added", entity_type="party", entity_id=str(id))
    session.commit()
    return party_repo.to_contact_api(row)


@router.delete("/parties/{id}/contacts/{childId}", status_code=204)
def delete_contact(id: uuid_mod.UUID, childId: uuid_mod.UUID, actor: Actor = Depends(require_permission("party:write"))):
    tenant_id = actor["tenant_id"]
    aggregate = party_repo.load_aggregate(tenant_id, id)
    target = next((c for c in aggregate.contacts if c.id == childId), None)
    if not target:
        raise not_found("Contact")

    email_contacts = [c for c in aggregate.contacts if c.email]
    if aggregate.party.status == "active" and len(email_contacts) == 1 and target.email:
        raise rule_violation(f"{aggregate.party.code} is active — it must keep at least one contact with an email address", code="EMAIL_CONTACT_REQUIRED")

    session.delete(target)
    party_repo.record_version(tenant_id=tenant_id, party_id=id, change_type="contact.removed", actor_id=actor["user_id"], actor_email=actor["email"])
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="party.contact.removed", entity_type="party", entity_id=str(id))
    session.commit()
    return Response(status_code=204)


# ---- bank accounts ------------------------------------------------------


@router.post("/parties/{id}/bank-accounts", status_code=201)
def add_bank_account(id: uuid_mod.UUID, body: BankAccountBody, actor: Actor = Depends(require_permission("party:write"))):
    tenant_id = actor["tenant_id"]
    party_repo.require_party(tenant_id, id)
    account_number = normalise_account_number(body.accountNumber)

    row = PartyBankAccount(
        tenant_id=tenant_id,
        party_id=id,
        account_name=body.accountName,
        account_number_encrypted=seal(account_number, settings.encryption_secret),
        account_number_last4=last_four(account_number),
        ifsc=body.ifsc,
        swift=body.swift,
        bank_name=body.bankName,
        branch=body.branch,
        # Approval flow removed for now: accounts are usable on entry (faithful
        # port of the Node service's current behavior).
        status="approved",
        created_by=actor["user_id"],
    )
    session.add(row)
    session.flush()

    party_repo.record_version(tenant_id=tenant_id, party_id=id, change_type="bank-account.added", actor_id=actor["user_id"], actor_email=actor["email"])
    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="party.bank-account.added",
        entity_type="party",
        entity_id=str(id),
        # The account number itself never reaches the audit table.
        meta={"accountName": body.accountName, "bankName": body.bankName, "last4": last_four(account_number), "status": "approved"},
    )
    session.commit()
    return party_repo.to_bank_account_api(row)


@router.post("/parties/{id}/bank-accounts/{childId}/approve")
def approve_bank_account(id: uuid_mod.UUID, childId: uuid_mod.UUID, body: ApproveBankAccountBody, actor: Actor = Depends(require_permission("party:approve"))):
    tenant_id = actor["tenant_id"]

    account = PartyBankAccount.query.filter_by(id=childId, party_id=id, tenant_id=tenant_id).first()
    if not account:
        raise not_found("Bank account")
    if account.status == "approved":
        raise conflict("This bank account is already approved", code="BANK_ACCOUNT_ALREADY_APPROVED")
    # Four-eyes: whoever entered the account cannot be the one who blesses it.
    if account.created_by and account.created_by == actor["user_id"]:
        raise rule_violation("Bank details must be approved by someone other than the person who entered them", code="SELF_APPROVAL_BLOCKED")

    account.status = "approved"
    account.approved_by = actor["user_id"]
    account.approved_at = datetime.now(timezone.utc)

    # Only one account can be the payable target; supersede the rest.
    PartyBankAccount.query.filter(PartyBankAccount.party_id == id, PartyBankAccount.id != childId, PartyBankAccount.status == "approved").update(
        {"status": "rejected", "rejected_reason": "Superseded by a newer approved account", "supersedes_id": childId}
    )

    party_repo.record_version(tenant_id=tenant_id, party_id=id, change_type="bank-account.approved", reason=body.reason, actor_id=actor["user_id"], actor_email=actor["email"])
    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="party.bank-account.approved",
        entity_type="party",
        entity_id=str(id),
        reason=body.reason,
        meta={"bankAccountId": str(childId), "last4": account.account_number_last4},
    )
    session.commit()
    return party_repo.to_bank_account_api(account)


@router.post("/parties/{id}/bank-accounts/{childId}/reject")
def reject_bank_account(id: uuid_mod.UUID, childId: uuid_mod.UUID, body: RejectBankAccountBody, actor: Actor = Depends(require_permission("party:approve"))):
    tenant_id = actor["tenant_id"]

    account = PartyBankAccount.query.filter_by(id=childId, party_id=id, tenant_id=tenant_id, status="pending").first()
    if not account:
        raise not_found("Pending bank account")

    account.status = "rejected"
    account.rejected_reason = body.reason

    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="party.bank-account.rejected",
        entity_type="party",
        entity_id=str(id),
        reason=body.reason,
        meta={"bankAccountId": str(childId)},
    )
    session.commit()
    return party_repo.to_bank_account_api(account)
