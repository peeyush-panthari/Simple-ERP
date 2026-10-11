"""Business entity (Simple's own legal entities, "Foundation > PO & Invoice")
queries + API projection - the seller identity resolved onto a purchase
order or invoice at render time."""

from __future__ import annotations

import uuid

from app.models.business_entity import BusinessEntity


def to_business_entity_api(row: BusinessEntity) -> dict:
    return {
        "id": str(row.id),
        "code": row.code,
        "name": row.name,
        "status": row.status,
        "isDefault": row.is_default,
        "addressLine1": row.address_line1,
        "addressLine2": row.address_line2,
        "city": row.city,
        "stateCode": row.state_code,
        "postalCode": row.postal_code,
        "country": row.country,
        "taxId": row.tax_id,
        "taxIdCountry": row.tax_id_country,
        "pan": row.pan,
        "contactEmail": row.contact_email,
        "contactPhone": row.contact_phone,
        "bankName": row.bank_name,
        "bankBranch": row.bank_branch,
        "bankAccountNumber": row.bank_account_number,
        "bankIfsc": row.bank_ifsc,
    }


def find_entity(tenant_id: uuid.UUID, entity_id: uuid.UUID) -> BusinessEntity | None:
    return BusinessEntity.query.filter_by(tenant_id=tenant_id, id=entity_id).first()


def find_entity_by_code(tenant_id: uuid.UUID, code: str) -> BusinessEntity | None:
    return BusinessEntity.query.filter_by(tenant_id=tenant_id, code=code).first()


def find_entities_by_codes(tenant_id: uuid.UUID, codes: list[str]) -> dict[str, BusinessEntity]:
    """Batched find_entity_by_code. That lookup compares the code exactly, not
    case-insensitively like the warehouse/party ones, so this key is the raw
    code - do not "fix" it here without changing the single-row path too."""
    wanted = {code for code in codes if code}
    if not wanted:
        return {}
    rows = BusinessEntity.query.filter(BusinessEntity.tenant_id == tenant_id, BusinessEntity.code.in_(wanted)).all()
    return {e.code: e for e in rows}


def get_default_entity(tenant_id: uuid.UUID) -> BusinessEntity | None:
    return BusinessEntity.query.filter_by(tenant_id=tenant_id, is_default=True, status="active").first()


def resolve_seller(tenant_id: uuid.UUID, entity_id: uuid.UUID | None) -> dict | None:
    """The seller identity for a PO/invoice document: the entity explicitly
    picked at creation, else the tenant's default - `None` if neither exists
    (a tenant that hasn't set up any business entity yet)."""
    entity = find_entity(tenant_id, entity_id) if entity_id else None
    entity = entity or get_default_entity(tenant_id)
    return to_business_entity_api(entity) if entity else None
