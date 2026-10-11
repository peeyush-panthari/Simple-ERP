"""Party aggregate loading, duplicate/tax-id probes, version recording, and
API projections. Ported from backend_py/app/services/party_repo.py -
`db.session`/`db.func` become the plain `session`/`func` this stack uses
everywhere (see app/core/db.py's docstring for why `Model.query` itself is
unchanged)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func

from app.core.config import settings
from app.core.db import session
from app.core.errors import not_found, rule_violation
from app.core.money import decimal_str
from app.models.party import Party
from app.models.party_address import PartyAddress
from app.models.party_bank_account import PartyBankAccount
from app.models.party_contact import PartyContact
from app.models.party_version import PartyVersion
from app.services.party_crypto import mask_account_number, open_


def _account_number_of(row: PartyBankAccount) -> str:
    try:
        return open_(row.account_number_encrypted, settings.encryption_secret)
    except Exception:
        return mask_account_number(row.account_number_last4)


@dataclass
class PartyAggregate:
    party: Party
    addresses: list[PartyAddress] = field(default_factory=list)
    contacts: list[PartyContact] = field(default_factory=list)
    bank_accounts: list[PartyBankAccount] = field(default_factory=list)


def find_party_by_id(tenant_id: uuid.UUID, party_id: uuid.UUID) -> Party | None:
    return Party.query.filter_by(tenant_id=tenant_id, id=party_id).first()


def require_party(tenant_id: uuid.UUID, party_id: uuid.UUID) -> Party:
    party = find_party_by_id(tenant_id, party_id)
    if not party:
        raise not_found("Party")
    return party


def find_party_by_code(tenant_id: uuid.UUID, code: str) -> Party | None:
    return Party.query.filter(Party.tenant_id == tenant_id, func.upper(Party.code) == code.upper()).first()


def find_parties_by_codes(tenant_id: uuid.UUID, codes: list[str]) -> dict[str, Party]:
    """Batched find_party_by_code - keyed by the UPPERCASED code."""
    wanted = {code.upper() for code in codes if code}
    if not wanted:
        return {}
    rows = Party.query.filter(Party.tenant_id == tenant_id, func.upper(Party.code).in_(wanted)).all()
    return {p.code.upper(): p for p in rows}


def find_duplicate(tenant_id: uuid.UUID, legal_name: str, tax_id: str | None, exclude_id: uuid.UUID | None = None) -> Party | None:
    q = Party.query.filter(Party.tenant_id == tenant_id, func.lower(Party.legal_name) == legal_name.lower())
    if tax_id:
        q = q.filter(func.upper(Party.tax_id) == tax_id.upper())
    else:
        q = q.filter(Party.tax_id.is_(None))
    if exclude_id:
        q = q.filter(Party.id != exclude_id)
    return q.first()


def find_by_legal_name(tenant_id: uuid.UUID, legal_name: str, exclude_id: uuid.UUID | None = None) -> Party | None:
    q = Party.query.filter(Party.tenant_id == tenant_id, func.lower(Party.legal_name) == legal_name.lower())
    if exclude_id:
        q = q.filter(Party.id != exclude_id)
    return q.first()


def find_tax_id_owner(tenant_id: uuid.UUID, tax_id: str, country: str, exclude_id: uuid.UUID | None = None) -> Party | None:
    q = Party.query.filter(
        Party.tenant_id == tenant_id,
        Party.tax_id_country == country,
        func.upper(Party.tax_id) == tax_id.upper(),
    )
    if exclude_id:
        q = q.filter(Party.id != exclude_id)
    return q.first()


def load_aggregate(tenant_id: uuid.UUID, party_id: uuid.UUID) -> PartyAggregate:
    party = require_party(tenant_id, party_id)
    addresses = (
        PartyAddress.query.filter_by(party_id=party_id)
        .order_by(PartyAddress.type, PartyAddress.is_default.desc(), PartyAddress.created_at)
        .all()
    )
    contacts = (
        PartyContact.query.filter_by(party_id=party_id).order_by(PartyContact.is_primary.desc(), PartyContact.created_at).all()
    )
    bank_accounts = PartyBankAccount.query.filter_by(party_id=party_id).order_by(PartyBankAccount.created_at.desc()).all()
    return PartyAggregate(party=party, addresses=addresses, contacts=contacts, bank_accounts=bank_accounts)


# ---- API projections --------------------------------------------------------


def to_address_api(row: PartyAddress) -> dict:
    return {
        "id": str(row.id),
        "type": row.type,
        "label": row.label,
        "line1": row.line1,
        "line2": row.line2,
        "city": row.city,
        "stateCode": row.state_code,
        "postalCode": row.postal_code,
        "country": row.country,
        "isDefault": row.is_default,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def to_contact_api(row: PartyContact) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "role": row.role,
        "email": row.email,
        "phone": row.phone,
        "isPrimary": row.is_primary,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def to_bank_account_api(row: PartyBankAccount) -> dict:
    return {
        "id": str(row.id),
        "accountName": row.account_name,
        "accountNumber": _account_number_of(row),
        "accountNumberMasked": mask_account_number(row.account_number_last4),
        "ifsc": row.ifsc,
        "swift": row.swift,
        "bankName": row.bank_name,
        "branch": row.branch,
        "status": row.status,
        "payable": row.status == "approved",
        "approvedBy": str(row.approved_by) if row.approved_by else None,
        "approvedAt": row.approved_at.isoformat() if row.approved_at else None,
        "rejectedReason": row.rejected_reason,
        "supersedesId": str(row.supersedes_id) if row.supersedes_id else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def to_party_api(row: Party) -> dict:
    return {
        "id": str(row.id),
        "code": row.code,
        "legalName": row.legal_name,
        "displayName": row.display_name,
        "type": row.type,
        "subtype": row.subtype,
        "status": row.status,
        "blocked": row.status == "blocked",
        "taxId": row.tax_id,
        "taxIdCountry": row.tax_id_country,
        "registrationNo": row.registration_no,
        "paymentTerms": row.payment_terms,
        "creditLimit": decimal_str(row.credit_limit),
        "creditUsed": decimal_str(row.credit_used),
        "currency": row.currency,
        "riskFlag": row.risk_flag,
        "industry": row.industry,
        "website": row.website,
        "notes": row.notes,
        "blockedReason": row.blocked_reason,
        "blockedAt": row.blocked_at.isoformat() if row.blocked_at else None,
        "activatedAt": row.activated_at.isoformat() if row.activated_at else None,
        "version": row.version,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def to_aggregate_api(aggregate: PartyAggregate) -> dict:
    return {
        **to_party_api(aggregate.party),
        "addresses": [to_address_api(a) for a in aggregate.addresses],
        "contacts": [to_contact_api(c) for c in aggregate.contacts],
        "bankAccounts": [to_bank_account_api(b) for b in aggregate.bank_accounts],
    }


def record_version(
    *,
    tenant_id: uuid.UUID,
    party_id: uuid.UUID,
    change_type: str,
    reason: str | None = None,
    actor_id: uuid.UUID,
    actor_email: str | None = None,
    correlation_id: str | None = None,
) -> int:
    """Appends a version row inside the caller's transaction (not yet committed)."""
    party = require_party(tenant_id, party_id)
    party.version += 1
    session.flush()

    aggregate = load_aggregate(tenant_id, party_id)
    snapshot = {**to_aggregate_api(aggregate), "version": party.version}

    session.add(
        PartyVersion(
            tenant_id=tenant_id,
            party_id=party_id,
            version=party.version,
            change_type=change_type,
            snapshot=snapshot,
            reason=reason,
            changed_by=str(actor_id),
            changed_by_email=actor_email,
            correlation_id=correlation_id,
        )
    )
    return party.version


# ---- direct-call helpers other domains import instead of an HTTP hop -------


def apply_credit_usage_for_party(
    tenant_id: uuid.UUID, party_id: uuid.UUID, *, delta, reference: str, allow_override: bool = False
) -> dict:
    """Serialised with FOR UPDATE so two concurrent orders cannot both squeeze
    under the same remaining limit. Caller must be inside a transaction."""
    from app.core.audit import audit
    from app.services.party_credit import apply_credit_usage

    party = session.query(Party).filter_by(tenant_id=tenant_id, id=party_id).with_for_update().first()
    if not party:
        raise not_found("Party")

    result = apply_credit_usage(
        credit_limit=party.credit_limit, credit_used=party.credit_used, delta=delta, allow_override=allow_override, party_code=party.code
    )

    before_used = decimal_str(party.credit_used)
    party.credit_used = result.credit_used
    audit(
        tenant_id=tenant_id,
        actor_id=None,
        actor_email=None,
        action="party.credit.applied",
        entity_type="party",
        entity_id=str(party_id),
        reason=f"Override: over limit by {result.over_by}" if result.over_by else None,
        meta={"before": {"creditUsed": before_used}, "after": {"creditUsed": result.credit_used, "delta": decimal_str(delta), "reference": reference}},
    )
    return {"partyId": str(party_id), "creditUsed": result.credit_used, "creditAvailable": result.credit_available, "overBy": result.over_by}


def get_payable_account(tenant_id: uuid.UUID, party_id: uuid.UUID) -> dict:
    account = (
        PartyBankAccount.query.filter_by(tenant_id=tenant_id, party_id=party_id, status="approved")
        .order_by(PartyBankAccount.approved_at.desc())
        .first()
    )
    if not account:
        raise rule_violation(
            "No approved bank account exists for this party — approve one before releasing a payment",
            code="NO_APPROVED_BANK_ACCOUNT",
        )
    return to_bank_account_api(account)
