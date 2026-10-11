"""The cross-service party summary contract - ported 1:1 from domain/summary.ts.

Its shape is fixed: procurement, order, finance and logistics modules will all
import build_summary() directly (once they exist) to decide "may I raise a
document against this party, and where do I send it?" - no HTTP round trip
needed in the monolith.
"""

from __future__ import annotations

import uuid

from app.services.party_credit import credit_position
from app.services.party_repo import PartyAggregate, load_aggregate
from app.services.party_tax_id import normalise_tax_id


def _pick_address(addresses, type_: str) -> dict | None:
    match = next((a for a in addresses if a.type == type_ and a.is_default), None) or next(
        (a for a in addresses if a.type == type_), None
    )
    if not match:
        return None
    return {
        "line1": match.line1,
        "line2": match.line2,
        "city": match.city,
        "stateCode": match.state_code,
        "postalCode": match.postal_code,
        "country": match.country,
    }


def build_summary(aggregate: PartyAggregate) -> dict:
    party, addresses, contacts, bank_accounts = aggregate.party, aggregate.addresses, aggregate.contacts, aggregate.bank_accounts

    billing = _pick_address(addresses, "billing")
    shipping = _pick_address(addresses, "shipping") or billing

    primary_contact = next((c for c in contacts if c.is_primary and c.email), None) or next(
        (c for c in contacts if c.email), None
    )

    credit = credit_position(credit_limit=party.credit_limit, credit_used=party.credit_used, status=party.status)

    tax_state = None
    if party.tax_id and party.tax_id_country:
        tax_state = normalise_tax_id(party.tax_id, party.tax_id_country).state_code

    return {
        "id": str(party.id),
        "code": party.code,
        "legalName": party.legal_name,
        "displayName": party.display_name,
        "type": party.type,
        "status": party.status,
        "blocked": party.status == "blocked",
        "paymentTerms": party.payment_terms,
        "currency": party.currency,
        "taxId": party.tax_id,
        "country": party.tax_id_country or (billing["country"] if billing else None),
        "stateCode": (billing["stateCode"] if billing else None) or tax_state,
        "creditLimit": credit.credit_limit,
        "creditUsed": credit.credit_used,
        "creditEligible": credit.eligible,
        "bankApproved": any(b.status == "approved" for b in bank_accounts),
        "email": primary_contact.email if primary_contact else None,
        "billingAddress": billing,
        "shippingAddress": shipping,
    }


def build_summary_by_id(tenant_id: uuid.UUID, party_id: uuid.UUID) -> dict:
    return build_summary(load_aggregate(tenant_id, party_id))
