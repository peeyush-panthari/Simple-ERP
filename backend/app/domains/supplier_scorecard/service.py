from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.core.db import session
from app.core.money import round_dp, to_decimal
from app.models.grn import Grn
from app.models.grn_line import GrnLine
from app.models.party import Party
from app.models.po_line import PoLine
from app.models.purchase_order import PurchaseOrder
from app.models.vendor_scorecard import VendorScorecard


def _grade_for_score(score: Decimal) -> tuple[str, str]:
    if score >= 90:
        return "A", "Preferred"
    if score >= 75:
        return "B", "Approved"
    if score >= 50:
        return "C", "Conditional"
    return "D", "At Risk"


def compute_vendor_scorecard(
    tenant_id: uuid.UUID,
    vendor_id: uuid.UUID,
    period: str = "all_time",
) -> dict:
    vendor = session.execute(
        select(Party).where(Party.tenant_id == tenant_id, Party.id == vendor_id)
    ).scalar_one_or_none()
    if not vendor:
        raise ValueError("Vendor party not found")

    # 1. Total POs
    total_pos = session.execute(
        select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.vendor_id == vendor_id,
        )
    ).scalar() or 0

    # 2. Total GRNs
    total_grns = session.execute(
        select(func.count(Grn.id)).where(
            Grn.tenant_id == tenant_id,
            Grn.vendor_id == vendor_id,
        )
    ).scalar() or 0

    # 3. GRN Lines inspection breakdown
    grn_lines_stmt = (
        select(GrnLine, Grn.received_date, PoLine.expected_date, PoLine.quantity)
        .join(Grn, GrnLine.grn_id == Grn.id)
        .outerjoin(PoLine, GrnLine.po_line_id == PoLine.id)
        .where(
            Grn.tenant_id == tenant_id,
            Grn.vendor_id == vendor_id,
            GrnLine.deleted_at.is_(None),
        )
    )
    records = session.execute(grn_lines_stmt).all()

    total_lines = len(records)
    total_received_qty = Decimal(0)
    total_accepted_qty = Decimal(0)
    total_rejected_qty = Decimal(0)
    otif_hits = 0
    evaluated_for_otif = 0

    for gl, received_date, promised_date, ordered_qty in records:
        rec_qty = to_decimal(gl.received_qty)
        acc_qty = to_decimal(gl.accepted_qty)
        rej_qty = to_decimal(gl.rejected_qty)

        total_received_qty += rec_qty
        total_accepted_qty += acc_qty
        total_rejected_qty += rej_qty

        # OTIF evaluation if we have delivery date
        if promised_date and received_date:
            evaluated_for_otif += 1
            on_time = received_date <= promised_date
            in_full = ordered_qty is None or (acc_qty >= to_decimal(ordered_qty))
            if on_time and in_full:
                otif_hits += 1

    # Calculations
    # Quality Score: accepted / received
    if total_received_qty > 0:
        quality_score = min(Decimal(100), (total_accepted_qty / total_received_qty) * Decimal(100))
    else:
        quality_score = Decimal(100)

    # OTIF Score
    if evaluated_for_otif > 0:
        otif_score = (Decimal(otif_hits) / Decimal(evaluated_for_otif)) * Decimal(100)
    elif total_grns > 0:
        otif_score = Decimal(90)  # Neutral baseline when dates aren't stamped on lines
    else:
        otif_score = Decimal(100)

    # Price Score (Baseline 98 - variance)
    price_score = Decimal("98.00")

    # Overall Score: 40% OTIF, 40% Quality, 20% Price
    overall_score = (otif_score * Decimal("0.40")) + (quality_score * Decimal("0.40")) + (price_score * Decimal("0.20"))
    overall_score = round_dp(min(Decimal(100), max(Decimal(0), overall_score)), 2)
    otif_score = round_dp(otif_score, 2)
    quality_score = round_dp(quality_score, 2)

    grade, grade_label = _grade_for_score(overall_score)

    # Persist or update in vendor_scorecards table
    now = datetime.now(timezone.utc)
    card = session.execute(
        select(VendorScorecard).where(
            VendorScorecard.tenant_id == tenant_id,
            VendorScorecard.vendor_id == vendor_id,
            VendorScorecard.period == period,
        )
    ).scalar_one_or_none()

    if not card:
        card = VendorScorecard(
            tenant_id=tenant_id,
            vendor_id=vendor_id,
            vendor_name=vendor.legal_name,
            period=period,
            overall_score=overall_score,
            otif_score=otif_score,
            quality_score=quality_score,
            price_score=price_score,
            grade=grade,
            total_pos=total_pos,
            total_grns=total_grns,
            total_lines_received=total_lines,
            total_lines_accepted=int(total_accepted_qty),
            total_lines_rejected=int(total_rejected_qty),
            avg_lead_time_days=Decimal(0),
            notes=f"Calculated from {total_grns} GRNs and {total_pos} POs",
            calculated_at=now,
        )
        session.add(card)
    else:
        card.vendor_name = vendor.legal_name
        card.overall_score = overall_score
        card.otif_score = otif_score
        card.quality_score = quality_score
        card.price_score = price_score
        card.grade = grade
        card.total_pos = total_pos
        card.total_grns = total_grns
        card.total_lines_received = total_lines
        card.total_lines_accepted = int(total_accepted_qty)
        card.total_lines_rejected = int(total_rejected_qty)
        card.notes = f"Calculated from {total_grns} GRNs and {total_pos} POs"
        card.calculated_at = now

    session.commit()

    return {
        "id": card.id,
        "vendorId": vendor.id,
        "vendorName": vendor.legal_name,
        "period": period,
        "overallScore": overall_score,
        "otifScore": otif_score,
        "qualityScore": quality_score,
        "priceScore": price_score,
        "grade": grade,
        "gradeLabel": grade_label,
        "totalPos": total_pos,
        "totalGrns": total_grns,
        "totalLinesReceived": total_lines,
        "totalLinesAccepted": int(total_accepted_qty),
        "totalLinesRejected": int(total_rejected_qty),
        "avgLeadTimeDays": Decimal(0),
        "notes": card.notes,
        "calculatedAt": card.calculated_at,
    }
