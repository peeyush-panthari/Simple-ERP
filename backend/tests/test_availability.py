"""New coverage - the Node inventory service had no tests for availability.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.availability import assert_sufficient, compute_availability


def test_available_to_promise_equals_on_hand_now_that_reserved_is_a_real_bucket():
    # Allocated stock has already physically left `available` into
    # `reserved` (a real ledger bucket) - availableToPromise is just an
    # alias of onHand now, nothing left to subtract.
    view = compute_availability({"available": "70", "reserved": "30", "quarantine": "0", "damaged": "0", "in_transit": "0", "expired": "0"})
    assert view["availableToPromise"] == "70.000000"
    assert view["onHand"] == "70.000000"
    assert view["reserved"] == "30.000000"


def test_damaged_expired_quarantine_in_transit_excluded_from_atp_but_reserved_counted_on_site():
    view = compute_availability({"available": "10", "reserved": "4", "quarantine": "5", "damaged": "3", "in_transit": "2", "expired": "1"})
    assert view["availableToPromise"] == "10.000000"
    assert view["totalOnSite"] == "23.000000"  # available + quarantine + damaged + expired + reserved (not in-transit)


def test_assert_sufficient_passes_when_requested_equals_atp():
    assert_sufficient(sku="RM-1", requested="10", available_to_promise="10", uom="KG")


def test_assert_sufficient_raises_with_shortfall_meta():
    with pytest.raises(ProblemError) as exc:
        assert_sufficient(sku="RM-1", requested="15", available_to_promise="10", uom="KG", warehouse_code="WH-1", batch_no="B1")
    assert exc.value.code == "INSUFFICIENT_STOCK"
    assert exc.value.meta["shortBy"] == "5.000000"
    assert "WH-1" in exc.value.detail
    assert "B1" in exc.value.detail
