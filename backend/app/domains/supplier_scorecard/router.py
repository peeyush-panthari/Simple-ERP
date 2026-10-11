from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.core.money import round_dp
from app.domains.supplier_scorecard.schemas import VendorScorecardOut, VendorScorecardSummary
from app.domains.supplier_scorecard.service import compute_vendor_scorecard
from app.models.party import Party

router = APIRouter(prefix="/api/v1/supplier-scorecards", tags=["supplier-scorecards"])


@router.get("/vendor/{vendor_id}", response_model=VendorScorecardOut)
def get_vendor_scorecard(
    vendor_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("party:read", "po:read", "sourcing:read"))],
    period: str = "all_time",
):
    try:
        data = compute_vendor_scorecard(actor["tenant_id"], vendor_id, period=period)
        return VendorScorecardOut(**data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary", response_model=VendorScorecardSummary)
def get_scorecards_summary(
    actor: Annotated[Actor, Depends(require_any_permission("party:read", "po:read", "sourcing:read"))],
):
    tenant_id = actor["tenant_id"]
    # Get all active vendor parties
    vendors = session.execute(
        select(Party).where(Party.tenant_id == tenant_id, Party.status == "active")
    ).scalars().all()
    # Filter only those that act as suppliers (or all parties if types aren't strictly segregated)
    cards = []
    tier_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    total_score = Decimal(0)

    for v in vendors:
        try:
            c = compute_vendor_scorecard(tenant_id, v.id)
            cards.append(VendorScorecardOut(**c))
            tier_counts[c["grade"]] = tier_counts.get(c["grade"], 0) + 1
            total_score += c["overallScore"]
        except Exception:
            continue

    avg_score = round_dp(total_score / Decimal(len(cards)), 2) if cards else Decimal(100)

    return VendorScorecardSummary(
        totalVendorsRated=len(cards),
        tierACount=tier_counts["A"],
        tierBCount=tier_counts["B"],
        tierCCount=tier_counts["C"],
        tierDCount=tier_counts["D"],
        averageOverallScore=avg_score,
        scorecards=cards,
    )
