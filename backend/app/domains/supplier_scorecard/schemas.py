from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class VendorScorecardOut(BaseModel):
    id: uuid.UUID | None = None
    vendorId: uuid.UUID
    vendorName: str
    period: str
    overallScore: Decimal
    otifScore: Decimal
    qualityScore: Decimal
    priceScore: Decimal
    grade: str  # 'A', 'B', 'C', 'D'
    gradeLabel: str  # 'Preferred', 'Approved', 'Conditional', 'At Risk'
    totalPos: int
    totalGrns: int
    totalLinesReceived: int
    totalLinesAccepted: int
    totalLinesRejected: int
    avgLeadTimeDays: Decimal
    notes: str | None = None
    calculatedAt: datetime

    class Config:
        from_attributes = True


class VendorScorecardSummary(BaseModel):
    totalVendorsRated: int
    tierACount: int
    tierBCount: int
    tierCCount: int
    tierDCount: int
    averageOverallScore: Decimal
    scorecards: list[VendorScorecardOut]
