"""FastAPI router for Approved Vendor List (AVL) & Supplier Governance.
Endpoints:
- GET /vendors: List AVL qualifications and vendor audit scores
- POST /vendors: Qualify vendor for product category or specific SKU
- PATCH /vendors/{id}/status: Update qualification status (approved, conditional_trial, disqualified)
- GET /certs: List compliance accreditation certificates with expiry radar
- POST /certs: Register quality certificate (ISO 9001, IATF 16949, RoHS)
- GET /check-po: Pre-PO placement validation gate checking vendor AVL clearance
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import select, or_, func

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.core.errors import bad_request, not_found
from app.models.party import Party
from app.models.phase2_modules import ApprovedVendor, VendorComplianceCert
from app.models.product import Product

router = APIRouter(prefix="/api/v1/avl", tags=["AVL Governance"])


class QualifyVendorRequest(BaseModel):
    vendor_party_id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
    category: Optional[str] = "Electronics & Assemblies"
    status: str = Field(default="approved")  # approved, conditional_trial, disqualified
    audit_score: Optional[int] = Field(default=85, ge=0, le=100)
    max_po_limit: Optional[float] = 1000000.0
    notes: Optional[str] = None


class RegisterCertRequest(BaseModel):
    vendor_party_id: uuid.UUID
    cert_type: str = Field(default="ISO_9001")  # ISO_9001, IATF_16949, ISO_14001, ROHS, REACH, GMP, CUSTOM
    certificate_number: str
    issuing_body: str
    issue_date: date
    expiry_date: date
    document_url: Optional[str] = None


@router.get("/vendors")
def list_approved_vendors(
    actor: Annotated[Actor, Depends(require_any_permission("avl_governance:read", "po:read", "*"))],
    status: Optional[str] = None,
):
    query = select(ApprovedVendor).where(ApprovedVendor.tenant_id == actor["tenant_id"])
    if status:
        query = query.where(ApprovedVendor.status == status)
    query = query.order_by(ApprovedVendor.created_at.desc())

    records = session.execute(query).scalars().all()

    vendors_map = {p.id: p for p in session.execute(select(Party).where(Party.tenant_id == actor["tenant_id"])).scalars().all()}
    prods_map = {p.id: p for p in session.execute(select(Product).where(Product.tenant_id == actor["tenant_id"])).scalars().all()}

    return {
        "vendors": [
            {
                "id": str(r.id),
                "vendor_party_id": str(r.vendor_party_id),
                "vendor_name": (vendors_map[r.vendor_party_id].display_name or vendors_map[r.vendor_party_id].legal_name) if r.vendor_party_id in vendors_map else "Vendor",
                "vendor_code": vendors_map[r.vendor_party_id].code if r.vendor_party_id in vendors_map else "V-001",
                "product_id": str(r.product_id) if r.product_id else None,
                "sku": prods_map[r.product_id].sku if r.product_id and r.product_id in prods_map else "Category-Wide",
                "category": r.category,
                "status": r.status,
                "audit_score": r.audit_score,
                "qualification_date": r.qualification_date.isoformat(),
                "max_po_limit": float(r.max_po_limit) if r.max_po_limit else None,
                "notes": r.notes,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]
    }


@router.post("/vendors")
def qualify_vendor(
    req: QualifyVendorRequest,
    actor: Annotated[Actor, Depends(require_any_permission("avl_governance:write", "*"))],
):
    vendor = session.get(Party, req.vendor_party_id)
    if not vendor:
        raise not_found("Vendor party not found.")

    avl = ApprovedVendor(
        tenant_id=actor["tenant_id"],
        vendor_party_id=req.vendor_party_id,
        product_id=req.product_id,
        category=req.category,
        status=req.status,
        audit_score=req.audit_score,
        qualification_date=date.today(),
        max_po_limit=Decimal(str(req.max_po_limit)) if req.max_po_limit else None,
        notes=req.notes,
        auditor_user_id=actor["user_id"],
    )
    session.add(avl)
    session.commit()

    return {
        "id": str(avl.id),
        "status": avl.status,
        "message": f"Supplier {vendor.display_name or vendor.code} qualified on AVL ({avl.status.upper()}).",
    }


@router.patch("/vendors/{avl_id}/status")
def update_vendor_status(
    avl_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("avl_governance:write", "*"))],
    status: str = Query(..., pattern="^(approved|conditional_trial|disqualified)$"),
):
    avl = session.execute(
        select(ApprovedVendor).where(ApprovedVendor.tenant_id == actor["tenant_id"], ApprovedVendor.id == avl_id)
    ).scalar_one_or_none()

    if not avl:
        raise not_found("AVL record not found.")

    avl.status = status
    session.commit()
    return {"message": f"AVL qualification status updated to {status.upper()}.", "status": status}


@router.get("/certs")
def list_vendor_certs(
    actor: Annotated[Actor, Depends(require_any_permission("avl_governance:read", "*"))],
    vendor_party_id: Optional[uuid.UUID] = None,
):
    query = select(VendorComplianceCert).where(VendorComplianceCert.tenant_id == actor["tenant_id"])
    if vendor_party_id:
        query = query.where(VendorComplianceCert.vendor_party_id == vendor_party_id)
    query = query.order_by(VendorComplianceCert.expiry_date.asc())

    certs = session.execute(query).scalars().all()
    vendors_map = {p.id: p for p in session.execute(select(Party).where(Party.tenant_id == actor["tenant_id"])).scalars().all()}

    today = date.today()
    res = []
    for c in certs:
        days_to_expiry = (c.expiry_date - today).days
        cert_status = "valid"
        if days_to_expiry < 0:
            cert_status = "expired"
        elif days_to_expiry < 30:
            cert_status = "expiring_soon"

        v_name = (vendors_map[c.vendor_party_id].display_name or vendors_map[c.vendor_party_id].legal_name) if c.vendor_party_id in vendors_map else "Vendor"

        res.append({
            "id": str(c.id),
            "vendor_party_id": str(c.vendor_party_id),
            "vendor_name": v_name,
            "cert_type": c.cert_type,
            "certificate_number": c.certificate_number,
            "issuing_body": c.issuing_body,
            "issue_date": c.issue_date.isoformat(),
            "expiry_date": c.expiry_date.isoformat(),
            "days_to_expiry": days_to_expiry,
            "status": cert_status,
            "document_url": c.document_url,
            "created_at": c.created_at.isoformat(),
        })

    return {"certificates": res}


@router.post("/certs")
def register_vendor_cert(
    req: RegisterCertRequest,
    actor: Annotated[Actor, Depends(require_any_permission("avl_governance:write", "*"))],
):
    vendor = session.get(Party, req.vendor_party_id)
    if not vendor:
        raise not_found("Vendor party not found.")

    cert = VendorComplianceCert(
        tenant_id=actor["tenant_id"],
        vendor_party_id=req.vendor_party_id,
        cert_type=req.cert_type,
        certificate_number=req.certificate_number,
        issuing_body=req.issuing_body,
        issue_date=req.issue_date,
        expiry_date=req.expiry_date,
        status="valid",
        document_url=req.document_url,
        verified_by_user_id=actor["user_id"],
    )
    session.add(cert)
    session.commit()

    return {
        "id": str(cert.id),
        "cert_type": cert.cert_type,
        "message": f"Compliance certificate {cert.certificate_number} registered successfully.",
    }


@router.get("/check-po")
def check_po_eligibility(
    vendor_party_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("avl_governance:read", "po:read", "*"))],
    product_id: Optional[uuid.UUID] = None,
    order_amount: Optional[float] = None,
):
    """Validation guard checking if supplier is approved to receive PO."""
    # Check AVL table
    query = select(ApprovedVendor).where(
        ApprovedVendor.tenant_id == actor["tenant_id"],
        ApprovedVendor.vendor_party_id == vendor_party_id,
    )
    if product_id:
        query = query.where(or_(ApprovedVendor.product_id == product_id, ApprovedVendor.product_id.is_(None)))

    avl = session.execute(query).scalars().first()

    if not avl:
        return {
            "eligible": False,
            "reason": "Supplier is not registered on the Approved Vendor List (AVL).",
            "status": "unapproved",
        }

    if avl.status == "disqualified":
        return {
            "eligible": False,
            "reason": "Supplier is DISQUALIFIED on the Approved Vendor List due to audit failure.",
            "status": "disqualified",
        }

    if order_amount and avl.max_po_limit and Decimal(str(order_amount)) > avl.max_po_limit:
        return {
            "eligible": False,
            "reason": f"Order amount exceeds supplier maximum PO ceiling of ₹{avl.max_po_limit}.",
            "status": "limit_exceeded",
        }

    return {
        "eligible": True,
        "reason": f"Supplier approved on AVL ({avl.status.upper()}). Audit score: {avl.audit_score}/100.",
        "status": avl.status,
    }
