"""Phase-3 infrastructure tests: proxy-aware client IP, the login rate limiter,
Redis caching, the publish-after-commit contract, the notification worker
(delivery, reconciliation onto the owning document, sweeping, idempotency) and
graceful behaviour when the broker is unreachable.

Real Postgres as everywhere else. Redis tests run against a throwaway
`redis-server` on a private port (skipped if the binary isn't installed).
There is no RabbitMQ on the test machine, so the broker itself is a recording
fake behind the same `Broker` interface the app uses - what is exercised for
real is everything on OUR side of it: when we publish, what we publish, and
what the worker does with a message.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core import messaging
from app.core.config import settings
from app.core.db import SessionLocal


def _auth_headers(client, admin):
    login = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


class FakeBroker:
    def __init__(self):
        self.published: list[tuple[str, dict]] = []
        self.fail = False

    def publish(self, queue, body):
        if self.fail:
            raise ConnectionError("broker down")
        self.published.append((queue, body))

    def healthy(self):
        return not self.fail


@pytest.fixture
def broker():
    fake = FakeBroker()
    messaging.set_broker(fake)
    yield fake
    messaging.set_broker(None)


@pytest.fixture
def async_mode(monkeypatch, broker):
    monkeypatch.setattr(settings, "async_notifications", True)
    return broker


@pytest.fixture(scope="module")
def redis_server():
    binary = shutil.which("redis-server")
    if not binary:
        pytest.skip("redis-server not installed")
    port = 6391
    proc = subprocess.Popen([binary, "--port", str(port), "--save", "", "--appendonly", "no"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import redis

    client = redis.Redis(port=port, socket_connect_timeout=1)
    for _ in range(50):
        try:
            client.ping()
            break
        except Exception:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.skip("redis-server did not start")
    yield f"redis://127.0.0.1:{port}/0"
    proc.terminate()
    proc.wait(timeout=5)


# ---- client IP ---------------------------------------------------------------


def _req(forwarded: str | None, peer: str = "10.0.0.9"):
    headers = {"x-forwarded-for": forwarded} if forwarded else {}
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=peer))


def test_client_ip_ignores_forwarded_header_without_trusted_proxies(monkeypatch):
    from app.core.client_ip import client_ip

    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    assert client_ip(_req("6.6.6.6")) == "10.0.0.9"  # spoofed header is not believed


def test_client_ip_takes_nth_from_right_behind_trusted_proxies(monkeypatch):
    from app.core.client_ip import client_ip

    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    assert client_ip(_req("6.6.6.6, 203.0.113.7")) == "203.0.113.7"  # attacker-prepended entry ignored
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    assert client_ip(_req("6.6.6.6, 203.0.113.7, 10.1.1.1")) == "203.0.113.7"
    assert client_ip(_req(None)) == "10.0.0.9"


# ---- rate limiting -------------------------------------------------------------


def test_login_is_rate_limited_with_problem_json(client):
    from app.core.rate_limit import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        codes = [client.post("/api/v1/auth/login", json={"email": "nobody@example.test", "password": "x" * 12}).status_code for _ in range(settings.rate_limit_login_per_minute + 3)]
        assert codes[: settings.rate_limit_login_per_minute] == [401] * settings.rate_limit_login_per_minute
        assert set(codes[settings.rate_limit_login_per_minute :]) == {429}
        blocked = client.post("/api/v1/auth/login", json={"email": "nobody@example.test", "password": "x" * 12})
        assert blocked.headers["content-type"].startswith("application/problem+json")
        assert blocked.json()["code"] == "RATE_LIMITED" and blocked.headers["retry-after"]
    finally:
        limiter.enabled = False
        limiter.reset()


def test_rate_limit_counts_in_redis_shared_across_limiter_instances(redis_server):
    from limits import parse
    from limits.storage import storage_from_string
    from limits.strategies import FixedWindowRateLimiter

    item = parse("2/minute")
    key = f"test-{uuid.uuid4().hex}"
    # Two separate limiter objects (= two API workers) share one budget.
    a = FixedWindowRateLimiter(storage_from_string(redis_server))
    b = FixedWindowRateLimiter(storage_from_string(redis_server))
    assert a.hit(item, key) and b.hit(item, key)
    assert not a.hit(item, key)


# ---- cache ---------------------------------------------------------------------


def test_cached_json_serves_from_redis_then_expires(monkeypatch, redis_server):
    from app.core import cache

    monkeypatch.setattr(settings, "redis_url", redis_server)
    monkeypatch.setattr(cache, "_client", None)
    calls = []

    def loader():
        calls.append(1)
        return {"n": len(calls)}

    key = f"t:{uuid.uuid4().hex}"
    assert cache.cached_json(key, 1, loader) == {"n": 1}
    assert cache.cached_json(key, 1, loader) == {"n": 1}  # hit
    assert len(calls) == 1
    time.sleep(1.2)
    assert cache.cached_json(key, 1, loader) == {"n": 2}  # expired -> reloaded
    assert cache.cached_json(key, 0, loader) == {"n": 3}  # ttl 0 never caches
    monkeypatch.setattr(cache, "_client", None)


def test_cache_degrades_to_live_compute_when_redis_is_down(monkeypatch):
    from app.core import cache

    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/0")  # nothing listens
    monkeypatch.setattr(cache, "_client", None)
    assert cache.cached_json("k", 30, lambda: {"live": True}) == {"live": True}
    assert cache.healthy() is False
    monkeypatch.setattr(cache, "_client", None)


def test_dashboard_is_cached_per_tenant_when_enabled(client, fresh_admin, monkeypatch, redis_server, default_tenant_id):
    from app.core import cache
    from app.services import analytics_repo

    monkeypatch.setattr(settings, "redis_url", redis_server)
    monkeypatch.setattr(settings, "dashboard_cache_seconds", 30)
    monkeypatch.setattr(cache, "_client", None)
    cache.get_redis().delete(f"dashboard:{default_tenant_id}")
    headers = _auth_headers(client, fresh_admin)
    calls = []
    real = analytics_repo.dashboard
    monkeypatch.setattr(analytics_repo, "dashboard", lambda tid: (calls.append(1), real(tid))[1])

    first = client.get("/api/v1/dashboard", headers=headers)
    second = client.get("/api/v1/dashboard", headers=headers)
    assert first.status_code == 200 and first.json() == second.json()
    assert len(calls) == 1
    cache.get_redis().delete(f"dashboard:{default_tenant_id}")
    monkeypatch.setattr(cache, "_client", None)


# ---- publish-after-commit ---------------------------------------------------------


def test_messages_publish_only_after_commit_and_never_after_rollback(broker):
    from sqlalchemy import text

    # Real call sites always publish inside a transaction that has done DB
    # work (they just flushed the queued row) - begin one the same way.
    SessionLocal.execute(text("select 1"))
    messaging.publish_after_commit("q", {"n": 1})
    assert broker.published == []  # nothing before commit
    SessionLocal.rollback()
    SessionLocal.commit()
    assert broker.published == []  # rolled back -> dropped, not resurrected by the next commit

    SessionLocal.execute(text("select 1"))
    messaging.publish_after_commit("q", {"n": 2})
    SessionLocal.commit()
    assert broker.published == [("q", {"n": 2})]


def test_publish_failure_is_swallowed_because_the_row_is_the_source_of_truth(broker):
    from sqlalchemy import text

    broker.fail = True
    SessionLocal.execute(text("select 1"))
    messaging.publish_after_commit("q", {"n": 1})
    SessionLocal.commit()  # must not raise
    assert broker.published == []


def test_real_pika_broker_raises_cleanly_when_rabbitmq_is_unreachable(monkeypatch):
    monkeypatch.setattr(settings, "rabbitmq_url", "amqp://guest:guest@127.0.0.1:1/")
    broker = messaging.PikaBroker()
    with pytest.raises(Exception):
        broker.publish("q", {"x": 1})
    assert broker.healthy() is False


# ---- async notifications end to end -------------------------------------------------


def _template(client, headers, key):
    assert client.put(f"/api/v1/templates/{key}", headers=headers, json={"subject": "S", "bodyText": "B"}).status_code == 200


def _cleanup_notes(template_key, address=None):
    from app.models.delivery_log import DeliveryLog
    from app.models.notification import Notification
    from app.models.notification_template import NotificationTemplate

    ids = [n.id for n in Notification.query.filter_by(template_key=template_key).all()]
    if ids:
        DeliveryLog.query.filter(DeliveryLog.notification_id.in_(ids)).delete(synchronize_session=False)
        Notification.query.filter(Notification.id.in_(ids)).delete(synchronize_session=False)
    NotificationTemplate.query.filter_by(key=template_key).delete(synchronize_session=False)
    SessionLocal.commit()


def test_async_send_returns_queued_publishes_after_commit_and_worker_delivers(client, fresh_admin, async_mode, monkeypatch, default_tenant_id):
    from app.services import notification_transport
    from app.worker import main as worker

    headers = _auth_headers(client, fresh_admin)
    key = f"test.async.{uuid.uuid4().hex[:6]}"
    _template(client, headers, key)

    sent_mail = []
    monkeypatch.setattr(notification_transport, "send_email", lambda **kw: (sent_mail.append(kw), {"ok": True, "provider": "smtp"})[1])

    resp = client.post("/api/v1/notifications/send", headers=headers, json={"template": key, "to": [f"a-{uuid.uuid4().hex[:5]}@example.test"]})
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "queued" and sent_mail == []  # the request itself delivered nothing
    note_id = resp.json()["id"]
    assert async_mode.published == [(settings.notification_queue, {"tenantId": str(default_tenant_id), "notificationId": note_id})]

    # The worker handles that exact message body.
    worker.handle_message(json.dumps(async_mode.published[0][1]).encode())
    assert len(sent_mail) == 1
    assert client.get("/api/v1/notifications", headers=headers, params={"status": "sent"}).json()["meta"]["total"] >= 1

    # Redelivery of the same message is harmless: sent exactly once.
    worker.handle_message(json.dumps(async_mode.published[0][1]).encode())
    assert len(sent_mail) == 1
    _cleanup_notes(key)


def test_worker_writes_outcome_back_onto_the_purchase_order(client, fresh_admin, async_mode, monkeypatch):
    from app.models.purchase_order import PurchaseOrder
    from app.services import notification_transport
    from app.worker import main as worker
    from tests.test_purchase_orders import _cleanup_po, _cleanup_product, _cleanup_vendor, _cleanup_warehouse, _setup

    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product = _setup(client, headers)
    # Give the vendor an email so issuing actually tries to send.
    email = f"vendor-{uuid.uuid4().hex[:6]}@example.test"
    assert client.post(f"/api/v1/parties/{vendor['id']}/contacts", headers=headers, json={"name": "AP Clerk", "email": email, "isPrimary": True}).status_code == 201
    po = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={"vendorId": vendor["id"], "warehouseId": warehouse["id"], "expectedDate": "2026-12-01", "lines": [{"productId": product["id"], "quantity": "5", "uom": "KG", "unitPrice": "100", "taxCode": "GST0"}]},
    ).json()

    send = client.post(f"/api/v1/purchase-orders/{po['id']}/send-email", headers=headers, json={})
    assert send.status_code == 200, send.text
    assert send.json()["emailState"] == "queued"
    message = next(body for queue, body in async_mode.published if queue == settings.notification_queue)

    monkeypatch.setattr(notification_transport, "send_email", lambda **kw: {"ok": True, "provider": "smtp"})
    worker.handle_message(json.dumps(message).encode())

    SessionLocal.expire_all()
    row = PurchaseOrder.query.filter_by(id=uuid.UUID(po["id"])).first()
    assert row.email_state == "sent" and row.email_sent_at is not None

    # A permanent failure is reconciled too.
    send_again = client.post(f"/api/v1/purchase-orders/{po['id']}/send-email", headers=headers, json={})
    assert send_again.json()["emailState"] == "queued"
    message2 = [body for queue, body in async_mode.published][-1]
    monkeypatch.setattr(notification_transport, "send_email", lambda **kw: {"ok": False, "provider": "smtp", "error": "550 mailbox unavailable", "permanent": True})
    worker.handle_message(json.dumps(message2).encode())
    SessionLocal.expire_all()
    row = PurchaseOrder.query.filter_by(id=uuid.UUID(po["id"])).first()
    assert row.email_state == "failed" and "550" in row.email_error

    from app.models.delivery_log import DeliveryLog
    from app.models.notification import Notification

    ids = [n.id for n in Notification.query.filter_by(related_type="purchase-order", related_id=po["id"]).all()]
    DeliveryLog.query.filter(DeliveryLog.notification_id.in_(ids)).delete(synchronize_session=False)
    Notification.query.filter(Notification.id.in_(ids)).delete(synchronize_session=False)
    SessionLocal.commit()
    _cleanup_po(po["id"])
    from app.models.party_contact import PartyContact

    PartyContact.query.filter_by(party_id=uuid.UUID(vendor["id"])).delete(synchronize_session=False)
    SessionLocal.commit()
    _cleanup_vendor(vendor["id"])
    _cleanup_warehouse(warehouse["id"])
    _cleanup_product(product["id"])


def test_sweeper_delivers_lost_and_due_rows_but_leaves_fresh_ones(client, fresh_admin, monkeypatch, default_tenant_id):
    """Broker was down at publish time: the row is queued with no message.
    The sweep still delivers it - but not one created moments ago (its own
    message may be in flight) and not one whose retry delay hasn't elapsed."""
    from app.models.notification import Notification
    from app.services import notification_transport
    from app.worker import main as worker

    headers = _auth_headers(client, fresh_admin)
    key = f"test.sweep.{uuid.uuid4().hex[:6]}"
    _template(client, headers, key)
    addr = f"s-{uuid.uuid4().hex[:5]}@example.test"
    ids = []
    for _ in range(3):
        r = client.post("/api/v1/notifications/send", headers=headers, json={"template": key, "to": [addr], "deferred": True})
        ids.append(uuid.UUID(r.json()["id"]))
    lost, fresh, backing_off = ids
    old = datetime.now(timezone.utc) - timedelta(minutes=5)
    Notification.query.filter_by(id=lost).update({"created_at": old, "next_attempt_at": old})
    Notification.query.filter_by(id=backing_off).update({"created_at": old, "next_attempt_at": datetime.now(timezone.utc) + timedelta(minutes=5)})
    SessionLocal.commit()

    # The sweep is global, so other due rows in a shared dev database (an emailed invoice, say) may be delivered
    # too - assert on this test's own recipient rather than on the sweep's total.
    sent = []
    monkeypatch.setattr(notification_transport, "send_email", lambda **kw: (sent.append(kw["to"]), {"ok": True, "provider": "smtp"})[1])
    assert worker.sweep_once() >= 1
    assert [to for to in sent if addr in to] == [[addr]]

    statuses = {n.id: n.status for n in Notification.query.filter(Notification.id.in_(ids)).all()}
    assert statuses == {lost: "sent", fresh: "queued", backing_off: "queued"}
    _cleanup_notes(key)


def test_worker_message_for_unknown_notification_is_a_noop_and_garbage_raises(default_tenant_id):
    from app.worker import main as worker

    assert worker.deliver(default_tenant_id, uuid.uuid4()) is None  # deleted/unknown row: ack and move on
    with pytest.raises(Exception):
        worker.handle_message(b"not json")  # -> consumer nacks to the dead-letter queue
