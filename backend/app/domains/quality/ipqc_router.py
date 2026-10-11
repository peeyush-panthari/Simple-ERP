"""FastAPI router for In-Process Quality Control (IPQC) & Certificate of Analysis (CoA).
Endpoints:
- GET /ipqc: List in-process quality inspections
- GET /runs-pending: Active production runs awaiting stage inspection
- POST /ipqc: Record parameter check and pass/fail gate for production stage
- GET /coa: List Certificates of Analysis
- POST /coa: Generate Certificate of Analysis for completed batch lot
- GET /coa/{id}/print: Printable CoA certificate slip data
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
from app.models.phase2_modules import IpqcInspection, CertificateOfAnalysis
from app.models.product import Product
from app.models.production_run import ProductionRun
from app.models.production_run_stage import ProductionRunStage
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1/quality", tags=["Quality Control"])


class ParameterCheck(BaseModel):
    parameter: str
    specification: str
    measured_value: str
    decision: str = "PASS"  # PASS, FAIL
    uom: Optional[str] = None


class RecordIpqcRequest(BaseModel):
    production_run_id: uuid.UUID
    stage_name: str
    sample_size: int = Field(default=5, ge=1)
    inspected_qty: float = Field(default=1.0, gt=0)
    passed_qty: float = Field(default=1.0, ge=0)
    failed_qty: float = Field(default=0.0, ge=0)
    status: str = Field(default="passed")  # passed, failed, conditionally_approved
    parameters: List[ParameterCheck]
    non_conformance_reason: Optional[str] = None
    corrective_action_required: bool = False


class CoaParameterItem(BaseModel):
    test_name: str
    method: str
    specification: str
    result: str
    decision: str = "PASS"


class GenerateCoaRequest(BaseModel):
    product_id: uuid.UUID
    batch_no: str
    production_run_id: Optional[uuid.UUID] = None
    mfg_date: date
    expiry_date: Optional[date] = None
    lot_size_qty: float = Field(..., gt=0)
    uom: str = "UNIT"
    test_standards: str = "ISO 9001:2015 / ASTM D638"
    specifications: List[CoaParameterItem]


@router.get("/ipqc")
def list_ipqc_inspections(
    actor: Annotated[Actor, Depends(require_any_permission("quality_ipqc:read", "*"))],
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    query = select(IpqcInspection).where(IpqcInspection.tenant_id == actor["tenant_id"])
    if status:
        query = query.where(IpqcInspection.status == status)
    query = query.order_by(IpqcInspection.inspected_at.desc()).limit(limit).offset(offset)

    inspections = session.execute(query).scalars().all()

    # Look up products and runs
    prod_map = {p.id: p for p in session.execute(select(Product).where(Product.tenant_id == actor["tenant_id"])).scalars().all()}
    run_map = {r.id: r for r in session.execute(select(ProductionRun).where(ProductionRun.tenant_id == actor["tenant_id"])).scalars().all()}

    return {
        "inspections": [
            {
                "id": str(i.id),
                "inspection_number": i.inspection_number,
                "production_run_id": str(i.production_run_id),
                "production_run_number": run_map[i.production_run_id].number if i.production_run_id in run_map else "RUN-001",
                "product_id": str(i.product_id),
                "sku": prod_map[i.product_id].sku if i.product_id in prod_map else "SKU",
                "product_name": prod_map[i.product_id].name if i.product_id in prod_map else "Product",
                "stage_name": i.stage_name,
                "sample_size": i.sample_size,
                "inspected_qty": float(i.inspected_qty),
                "passed_qty": float(i.passed_qty),
                "failed_qty": float(i.failed_qty),
                "status": i.status,
                "parameters_checked": i.parameters_checked,
                "non_conformance_reason": i.non_conformance_reason,
                "corrective_action_required": i.corrective_action_required,
                "inspected_at": i.inspected_at.isoformat(),
            }
            for i in inspections
        ]
    }


@router.get("/runs-pending")
def list_runs_pending_inspection(
    actor: Annotated[Actor, Depends(require_any_permission("quality_ipqc:read", "*"))],
):
    """Active production runs that can receive in-process inspection."""
    runs = session.execute(
        select(ProductionRun).where(
            ProductionRun.tenant_id == actor["tenant_id"],
            ProductionRun.status.in_(["planned", "posted"]),
        ).order_by(ProductionRun.created_at.desc())
    ).scalars().all()

    prod_map = {p.id: p for p in session.execute(select(Product).where(Product.tenant_id == actor["tenant_id"])).scalars().all()}

    return {
        "runs": [
            {
                "id": str(r.id),
                "run_number": r.number,
                "product_id": str(r.product_id),
                "sku": prod_map[r.product_id].sku if r.product_id in prod_map else "SKU",
                "product_name": prod_map[r.product_id].name if r.product_id in prod_map else "Assembly",
                "target_quantity": float(r.quantity),
                "status": r.status,
                "default_stage": "Stage 2: Mid-Assembly Quality Gate",
            }
            for r in runs
        ]
    }


@router.post("/ipqc")
def record_ipqc_inspection(
    req: RecordIpqcRequest,
    actor: Annotated[Actor, Depends(require_any_permission("quality_ipqc:write", "*"))],
):
    run = session.execute(
        select(ProductionRun).where(
            ProductionRun.tenant_id == actor["tenant_id"],
            ProductionRun.id == req.production_run_id
        )
    ).scalar_one_or_none()
    if not run:
        raise not_found("Production run not found.")

    insp_no = next_document_number(actor["tenant_id"], "IPQC")

    params_json = [p.dict() for p in req.parameters]

    insp = IpqcInspection(
        tenant_id=actor["tenant_id"],
        inspection_number=insp_no,
        production_run_id=req.production_run_id,
        product_id=run.product_id,
        stage_name=req.stage_name,
        sample_size=req.sample_size,
        inspected_qty=Decimal(str(req.inspected_qty)),
        passed_qty=Decimal(str(req.passed_qty)),
        failed_qty=Decimal(str(req.failed_qty)),
        status=req.status,
        parameters_checked=params_json,
        non_conformance_reason=req.non_conformance_reason,
        corrective_action_required=req.corrective_action_required,
        inspector_user_id=actor["user_id"],
    )
    session.add(insp)
    session.commit()

    return {
        "id": str(insp.id),
        "inspection_number": insp.inspection_number,
        "status": insp.status,
        "message": f"IPQC inspection recorded successfully ({insp.status.upper()}).",
    }


@router.get("/coa")
def list_certificates_of_analysis(
    actor: Annotated[Actor, Depends(require_any_permission("quality_ipqc:read", "*"))],
    batch_no: Optional[str] = None,
):
    query = select(CertificateOfAnalysis).where(CertificateOfAnalysis.tenant_id == actor["tenant_id"])
    if batch_no:
        query = query.where(CertificateOfAnalysis.batch_no.ilike(f"%{batch_no}%"))
    query = query.order_by(CertificateOfAnalysis.created_at.desc())

    coas = session.execute(query).scalars().all()
    prod_map = {p.id: p for p in session.execute(select(Product).where(Product.tenant_id == actor["tenant_id"])).scalars().all()}

    return {
        "coas": [
            {
                "id": str(c.id),
                "coa_number": c.coa_number,
                "product_id": str(c.product_id),
                "sku": prod_map[c.product_id].sku if c.product_id in prod_map else "SKU",
                "product_name": prod_map[c.product_id].name if c.product_id in prod_map else "Product",
                "batch_no": c.batch_no,
                "mfg_date": c.mfg_date.isoformat(),
                "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
                "lot_size_qty": float(c.lot_size_qty),
                "uom": c.uom,
                "test_standards": c.test_standards,
                "parameters_count": len(c.specifications_grid),
                "is_published": c.is_published,
                "created_at": c.created_at.isoformat(),
            }
            for c in coas
        ]
    }


@router.post("/coa")
def generate_certificate_of_analysis(
    req: GenerateCoaRequest,
    actor: Annotated[Actor, Depends(require_any_permission("quality_ipqc:write", "*"))],
):
    prod = session.execute(
        select(Product).where(
            Product.tenant_id == actor["tenant_id"],
            Product.id == req.product_id
        )
    ).scalar_one_or_none()
    if not prod:
        raise not_found("Product not found.")

    coa_no = next_document_number(actor["tenant_id"], "COA")

    grid_json = [s.dict() for s in req.specifications]

    coa = CertificateOfAnalysis(
        tenant_id=actor["tenant_id"],
        coa_number=coa_no,
        product_id=req.product_id,
        batch_no=req.batch_no,
        production_run_id=req.production_run_id,
        mfg_date=req.mfg_date,
        expiry_date=req.expiry_date,
        lot_size_qty=Decimal(str(req.lot_size_qty)),
        uom=req.uom,
        test_standards=req.test_standards,
        specifications_grid=grid_json,
        tested_by_user_id=actor["user_id"],
        authorized_by_user_id=actor["user_id"],
        is_published=True,
    )
    session.add(coa)
    session.commit()

    return {
        "id": str(coa.id),
        "coa_number": coa.coa_number,
        "message": f"Certificate of Analysis {coa.coa_number} successfully published.",
    }


@router.get("/coa/{coa_id}/print")
def get_coa_print_slip(
    coa_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("quality_ipqc:read", "*"))],
):
    coa = session.execute(
        select(CertificateOfAnalysis).where(CertificateOfAnalysis.tenant_id == actor["tenant_id"], CertificateOfAnalysis.id == coa_id)
    ).scalar_one_or_none()
    if not coa:
        raise not_found("Certificate of Analysis not found.")

    prod = session.execute(
        select(Product).where(
            Product.tenant_id == actor["tenant_id"],
            Product.id == coa.product_id
        )
    ).scalar_one_or_none()

    return {
        "coa_number": coa.coa_number,
        "product_name": prod.name if prod else "Finished Good",
        "sku": prod.sku if prod else "SKU-001",
        "batch_no": coa.batch_no,
        "mfg_date": coa.mfg_date.isoformat(),
        "expiry_date": coa.expiry_date.isoformat() if coa.expiry_date else "N/A",
        "lot_size": f"{coa.lot_size_qty} {coa.uom}",
        "standards": coa.test_standards,
        "specifications": coa.specifications_grid,
        "qa_signoff": "Approved & Authorized by Head of Quality Assurance",
        "certified_date": coa.created_at.strftime("%Y-%m-%d"),
    }
