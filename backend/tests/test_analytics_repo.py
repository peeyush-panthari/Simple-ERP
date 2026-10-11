"""New coverage for the control-tower dashboard's from-scratch logic (order
funnel status-bucketing, live cycle-time computation, the panel() degraded-
dependency wrapper) - see app/services/analytics_repo.py's module docstring
for why this isn't a port of Node's event-projection pipeline.

Each test gets its own freshly-generated tenant_id (tenant_id columns carry
no FK constraint anywhere in this schema) rather than the shared dev
database's default_tenant_id, so order_funnel()/cycle_times()'s tenant-wide
aggregates are fully isolated from other tests and from manual curl testing
against the same dev database - absolute assertions are safe here."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.flaskcompat import db as _db
from app.services import analytics_repo


@pytest.fixture
def party_and_warehouse(app):
    from app.models.party import Party
    from app.models.warehouse import Warehouse

    with app.app_context():
        tenant_id = uuid.uuid4()
        suffix = uuid.uuid4().hex[:8]
        party = Party(tenant_id=tenant_id, code=f"PTY-TST-{suffix}", legal_name="Analytics Test Co", display_name="Analytics Test Co", type="customer", status="active")
        warehouse = Warehouse(tenant_id=tenant_id, code=f"WH-TST-{suffix}", name="Analytics Test Warehouse", status="active")
        _db.session.add_all([party, warehouse])
        _db.session.commit()
        yield {"tenant_id": tenant_id, "party_id": party.id, "warehouse_id": warehouse.id}

        # These tests run against the shared dev database with no transaction
        # rollback, so without this every run left its orders, invoices and
        # payments behind for good. The tenant_id is generated per test and
        # used by nothing else, which makes deleting by it safe. Children
        # first - the FKs point upward.
        from app.models.ar_invoice import ArInvoice
        from app.models.order import Order
        from app.models.payment import Payment
        from app.models.payment_allocation import PaymentAllocation

        for model in (PaymentAllocation, Payment, ArInvoice, Order, Warehouse, Party):
            model.query.filter_by(tenant_id=tenant_id).delete(synchronize_session=False)
        _db.session.commit()


def _make_order(ctx, *, status: str, total: str = "1000", order_date=None, shipped_at=None, number=None):
    from app.models.order import Order

    order_date = order_date or date.today()
    order = Order(
        tenant_id=ctx["tenant_id"],
        number=number or f"SO-TST-{uuid.uuid4().hex[:8]}",
        customer_id=ctx["party_id"],
        customer_name="Analytics Test Co",
        status=status,
        order_date=order_date,
        promised_date=order_date + timedelta(days=7),
        warehouse_id=ctx["warehouse_id"],
        total=total,
        shipped_at=shipped_at,
    )
    _db.session.add(order)
    _db.session.flush()
    return order


def _counts_by_stage(funnel: list[dict]) -> dict[str, int]:
    return {f["stage"]: f["count"] for f in funnel}


class TestOrderFunnel:
    def test_buckets_by_status_into_the_five_node_stages(self, app, party_and_warehouse):
        with app.app_context():
            # No 'draft' - 'confirmed' is the initial state and buckets into
            # "Confirmed" (see analytics_repo._STATUS_TO_STAGE).
            _make_order(party_and_warehouse, status="confirmed", total="200")
            _make_order(party_and_warehouse, status="allocated", total="250")
            _make_order(party_and_warehouse, status="partially_allocated", total="300")
            _make_order(party_and_warehouse, status="shipped", total="400")
            _make_order(party_and_warehouse, status="partially_shipped", total="450")
            _make_order(party_and_warehouse, status="invoiced", total="600")
            _make_order(party_and_warehouse, status="fulfilled", total="700")
            _make_order(party_and_warehouse, status="partially_fulfilled", total="750")
            _db.session.commit()

            funnel = analytics_repo.order_funnel(party_and_warehouse["tenant_id"])
            by_stage = _counts_by_stage(funnel)
            by_stage_value = {f["stage"]: f["value"] for f in funnel}

            assert by_stage["Confirmed"] == 1
            assert by_stage["Under production"] == 2  # allocated + partially_allocated
            assert by_stage["Dispatched"] == 2  # shipped + partially_shipped
            assert by_stage["Invoiced"] == 1
            assert by_stage["Fulfilled"] == 2  # fulfilled + partially_fulfilled
            assert by_stage_value["Fulfilled"] == "1450.000000"  # 700 + 750

    def test_cancelled_orders_are_excluded_entirely(self, app, party_and_warehouse):
        with app.app_context():
            _make_order(party_and_warehouse, status="cancelled", total="9999")
            _db.session.commit()

            funnel = analytics_repo.order_funnel(party_and_warehouse["tenant_id"])
            assert sum(_counts_by_stage(funnel).values()) == 0

    def test_all_five_stages_always_present_even_when_empty(self, app, party_and_warehouse):
        with app.app_context():
            funnel = analytics_repo.order_funnel(party_and_warehouse["tenant_id"])
            stages = [f["stage"] for f in funnel]
            assert stages == ["Confirmed", "Under production", "Dispatched", "Invoiced", "Fulfilled"]


class TestCycleTimes:
    def test_sample_size_only_counts_orders_with_shipped_at_set(self, app, party_and_warehouse):
        with app.app_context():
            _make_order(party_and_warehouse, status="confirmed")  # never shipped
            _make_order(party_and_warehouse, status="shipped", shipped_at=datetime.now(timezone.utc))
            _db.session.commit()

            result = analytics_repo.cycle_times(party_and_warehouse["tenant_id"])
            assert result["sampleSize"] == 1

    def test_order_to_ship_averages_days_between_order_date_and_shipped_at(self, app, party_and_warehouse):
        with app.app_context():
            placed = date.today() - timedelta(days=5)
            shipped = datetime.now(timezone.utc)
            _make_order(party_and_warehouse, status="shipped", order_date=placed, shipped_at=shipped)
            _db.session.commit()

            result = analytics_repo.cycle_times(party_and_warehouse["tenant_id"])
            assert result["orderToShip"] == "5.00"

    def test_orders_outside_the_180_day_window_are_excluded(self, app, party_and_warehouse):
        with app.app_context():
            old_date = date.today() - timedelta(days=200)
            _make_order(party_and_warehouse, status="shipped", order_date=old_date, shipped_at=datetime.now(timezone.utc))
            _db.session.commit()

            result = analytics_repo.cycle_times(party_and_warehouse["tenant_id"])
            assert result["sampleSize"] == 0

    def test_invoice_to_cash_only_counts_orders_with_a_recorded_payment(self, app, party_and_warehouse):
        """Unlike finance.py's DSO calc (which defaults an unpaid invoice's
        effective date to today()), Node's order_cycle-based invoiceToCash
        only reflects orders that actually have a settled_at - an unpaid
        order contributes nothing to the average, not a same-day value."""
        from app.models.ar_invoice import ArInvoice

        with app.app_context():
            shipped = datetime.now(timezone.utc)
            order = _make_order(party_and_warehouse, status="invoiced", shipped_at=shipped)
            ar = ArInvoice(
                tenant_id=party_and_warehouse["tenant_id"],
                number=f"INV-TST-{uuid.uuid4().hex[:8]}",
                order_id=order.id,
                customer_id=party_and_warehouse["party_id"],
                customer_name="Analytics Test Co",
                invoice_date=date.today(),
                due_date=date.today() + timedelta(days=15),
                period=date.today().strftime("%Y-%m"),
                amount="1000",
            )
            _db.session.add(ar)
            _db.session.commit()

            result = analytics_repo.cycle_times(party_and_warehouse["tenant_id"])
            assert result["sampleSize"] == 1
            assert result["shipToInvoice"] is not None  # the invoice link itself counts
            assert result["invoiceToCash"] is None  # but no payment was ever recorded
            assert result["orderToCash"] is None

    def test_invoice_to_cash_counts_orders_once_a_payment_is_allocated(self, app, party_and_warehouse):
        from app.models.ar_invoice import ArInvoice
        from app.models.payment import Payment
        from app.models.payment_allocation import PaymentAllocation

        with app.app_context():
            shipped = datetime.now(timezone.utc)
            invoice_date = date.today() - timedelta(days=3)
            order = _make_order(party_and_warehouse, status="invoiced", shipped_at=shipped)
            ar = ArInvoice(
                tenant_id=party_and_warehouse["tenant_id"],
                number=f"INV-TST-{uuid.uuid4().hex[:8]}",
                order_id=order.id,
                customer_id=party_and_warehouse["party_id"],
                customer_name="Analytics Test Co",
                invoice_date=invoice_date,
                due_date=invoice_date + timedelta(days=15),
                period=invoice_date.strftime("%Y-%m"),
                amount="1000",
            )
            _db.session.add(ar)
            _db.session.flush()

            payment = Payment(
                tenant_id=party_and_warehouse["tenant_id"],
                number=f"PAY-TST-{uuid.uuid4().hex[:8]}",
                direction="inbound",
                party_id=party_and_warehouse["party_id"],
                party_name="Analytics Test Co",
                payment_date=date.today(),
                period=date.today().strftime("%Y-%m"),
                amount="1000",
            )
            _db.session.add(payment)
            _db.session.flush()
            _db.session.add(PaymentAllocation(tenant_id=party_and_warehouse["tenant_id"], payment_id=payment.id, ar_invoice_id=ar.id, amount="1000"))
            _db.session.commit()

            result = analytics_repo.cycle_times(party_and_warehouse["tenant_id"])
            assert result["invoiceToCash"] == "3.00"
            assert result["orderToCash"] is not None


class TestPanel:
    def test_available_panel_carries_its_data(self):
        result = analytics_repo.panel("finance", True, {"x": 1})
        assert result == {"available": True, "source": "finance", "data": {"x": 1}, "error": None}

    def test_unavailable_panel_carries_no_data_and_an_error(self):
        result = analytics_repo.panel("ticket", False, None, "not built yet")
        assert result == {"available": False, "source": "ticket", "data": None, "error": "not built yet"}
