"""Publish gating - ported 1:1 from domain/publish.ts.

Every blocker is reported at once - a publish flow that reveals one missing
field per attempt is the single most complained-about thing in master data
entry.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import rule_violation
from app.services.uom import is_known_uom


@dataclass
class PublishCandidate:
    sku: str
    name: str
    type: str
    category_id: str | None
    uom: str
    status: str
    image_count: int
    spec_count: int
    sellable: bool
    has_approved_bom: bool | None


def publish_blockers(candidate: PublishCandidate) -> list[dict]:
    errors: list[dict] = []

    if not candidate.name.strip():
        errors.append({"field": "name", "message": "A product name is required"})
    if not candidate.category_id:
        errors.append({"field": "categoryId", "message": "A category is required before publishing"})
    if not is_known_uom(candidate.uom):
        errors.append({"field": "uom", "message": f'"{candidate.uom}" is not a configured unit of measure'})

    if candidate.type == "finished_good" and candidate.image_count == 0:
        errors.append({"field": "images", "message": "Finished goods need at least one image before publishing"})
    if candidate.type == "raw_material" and candidate.spec_count == 0:
        errors.append(
            {"field": "specs", "message": "Raw materials need at least one specification (grade, purity, dimension …) before publishing"}
        )

    if candidate.type == "finished_good" and candidate.sellable and candidate.has_approved_bom is False:
        errors.append(
            {
                "field": "sellable",
                "message": "No approved BOM exists for this finished good — approve a BOM version, or publish it as not-sellable for now",
            }
        )

    return errors


def assert_publishable(candidate: PublishCandidate) -> None:
    if candidate.status == "deprecated":
        raise rule_violation(f"{candidate.sku} is deprecated — publish a replacement SKU rather than reviving this one", code="PRODUCT_DEPRECATED")
    errors = publish_blockers(candidate)
    if errors:
        joined = "; ".join(e["message"] for e in errors)
        raise rule_violation(f"{candidate.sku} cannot be published yet: {joined}", code="PRODUCT_NOT_PUBLISHABLE", meta={"errors": errors})
