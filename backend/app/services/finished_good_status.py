"""FinishedGoodItem.status lifecycle - shared by the manual allocation routes
(app/routes/orders.py) and the shipping/release paths in
app/services/inventory_ledger.py, so both agree on what an item's status
should read after allocated_qty/shipped_qty change.

`status` doubles as a condition value (quarantine/damaged/expired) and a
reservation/shipping lifecycle value (available/reserved/partially_reserved/
shipped) - condition always wins, allocation/shipping never override it.
"""

from __future__ import annotations

from app.models.finished_good_item import FinishedGoodItem
from app.core.money import to_decimal

_CONDITION_STATUSES = ("quarantine", "damaged", "expired")


def recompute_status(item: FinishedGoodItem) -> None:
    if item.status in _CONDITION_STATUSES:
        return

    remaining = to_decimal(item.quantity) - to_decimal(item.shipped_qty)
    if remaining <= 0:
        item.status = "shipped"
        return

    allocated = to_decimal(item.allocated_qty)
    if allocated <= 0:
        item.status = "available"
    elif allocated >= remaining:
        item.status = "reserved"
    else:
        # UNIT-kind items always have quantity == 1, so allocated_qty is
        # either 0 or 1 - never partial. Only a lot can be part-allocated.
        item.status = "partially_reserved" if item.kind == "lot" else "reserved"
