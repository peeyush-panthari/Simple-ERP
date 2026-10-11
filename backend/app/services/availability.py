"""The availability model - ported 1:1 from domain/availability.ts, updated
for a real `reserved` bucket.

  on hand    = quantity physically in the `available` bucket
  reserved   = quantity physically in the `reserved` bucket (allocated to an
               order, not yet shipped - a real ledger posting now, not a
               read-time subtraction)
  available  = on hand (already net of reserved, by construction)

`availableToPromise` is kept as an alias of `onHand` for API-shape
stability - now that allocated stock has physically left `available`,
there's nothing left to subtract. Damaged, expired, quarantined and
in-transit stock is deliberately NOT part of availability: it exists, it is
worth money, and it cannot be shipped.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import rule_violation
from app.core.money import decimal_str, to_decimal


@dataclass
class BucketQuantities:
    available: str = "0"
    quarantine: str = "0"
    damaged: str = "0"
    in_transit: str = "0"
    expired: str = "0"
    reserved: str = "0"


def compute_availability(buckets: dict) -> dict:
    available = to_decimal(buckets.get("available", 0))
    quarantine = to_decimal(buckets.get("quarantine", 0))
    damaged = to_decimal(buckets.get("damaged", 0))
    in_transit = to_decimal(buckets.get("in_transit", buckets.get("inTransit", 0)))
    expired = to_decimal(buckets.get("expired", 0))
    reserved = to_decimal(buckets.get("reserved", 0))

    return {
        "available": decimal_str(available),
        "quarantine": decimal_str(quarantine),
        "damaged": decimal_str(damaged),
        "inTransit": decimal_str(in_transit),
        "expired": decimal_str(expired),
        "onHand": decimal_str(available),
        "reserved": decimal_str(reserved),
        "availableToPromise": decimal_str(available),
        "totalOnSite": decimal_str(available + quarantine + damaged + expired + reserved),
    }


def assert_sufficient(*, sku: str, requested, available_to_promise, uom: str, warehouse_code: str | None = None, batch_no: str | None = None) -> None:
    requested_d = to_decimal(requested)
    atp = to_decimal(available_to_promise)
    if requested_d <= atp:
        return

    where = f" at {warehouse_code}" if warehouse_code else ""
    batch = f" batch {batch_no}" if batch_no else ""
    raise rule_violation(
        f"Only {decimal_str(atp)} {uom} of {sku}{batch}{where} is available to promise — "
        f"{decimal_str(requested_d)} {uom} was requested. Reserved, damaged, expired, quarantined and "
        "in-transit stock cannot be used for fulfilment",
        code="INSUFFICIENT_STOCK",
        meta={"sku": sku, "requested": decimal_str(requested_d), "availableToPromise": decimal_str(atp), "shortBy": decimal_str(requested_d - atp)},
    )


BUCKETS = ("available", "quarantine", "damaged", "in_transit", "expired", "reserved")
