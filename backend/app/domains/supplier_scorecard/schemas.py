from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class VendorScorecardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class VendorScorecardSummary(BaseModel):
    totalVendorsRated: int
    tierACount: int
    tierBCount: int
    tierCCount: int
    tierDCount: int
    averageOverallScore: Decimal
    scorecards: list[VendorScorecardOut]
