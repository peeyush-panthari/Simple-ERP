"""Background worker: `python -m app.worker`. Delivers notifications and renders PDFs.

Notifications - two things run side by side in this one process:

* a RabbitMQ consumer on `settings.notification_queue`. Each message names a
  committed `queued` notification row (see core/messaging.py); the worker
  delivers it exactly as the inline path would (SMTP / Twilio, the same retry
  bookkeeping and delivery-log rows), then writes the outcome back onto the
  invoice / PO / RFQ invitation / dispatch that asked for the email.
* a sweeper thread that every `worker_sweep_seconds` delivers any `queued`
  notification that is due (`next_attempt_at` passed) and older than a few
  seconds. This is what makes the queue robust: it retries transient failures
  with the backoff already recorded on the row, and it picks up rows whose
  message was never published because the broker was down. It talks to
  Postgres only, so it keeps working through a RabbitMQ outage.

Delivering is idempotent - `deliver_now` locks the row and only acts on
queued/sending/failed ones - so a duplicate message, or the consumer and the
sweeper reaching the same row, sends once.

Failure handling: a handler exception `nack`s without requeue, which sends the
message to `<queue>.dead` (see messaging.declare_queues) instead of looping.

PDFs (ASYNC_PDF=true) follow the same pattern on `settings.document_queue`: a message
names a committed, not-yet-rendered `documents` row, the worker renders and stores it
(`document_repo.complete_render` - idempotent, row-locked), and the same sweep picks up
rows whose message was lost. A download that arrives first renders the row itself, so
the worker only ever makes things faster, never possible.
"""

from __future__ import annotations

import json
import logging
import signal
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pika

from app.core import messaging
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.document import Document
from app.models.notification import Notification
from app.services import document_repo, notification_repo
from app.services.notification_reconcile import reconcile_related

logger = logging.getLogger("worker")

# A freshly-queued row is left to its own message for this long before the
# sweeper considers it "lost".
SWEEP_GRACE_SECONDS = 15

stop_event = threading.Event()


def deliver(tenant_id: uuid.UUID, notification_id: uuid.UUID) -> str | None:
    """Deliver one notification and reconcile its owner. Returns the final
    notification status, or None if the row doesn't exist."""
    try:
        notification_repo.deliver_now(tenant_id, notification_id)
        note = Notification.query.filter_by(tenant_id=tenant_id, id=notification_id).first()
        if note is None:
            return None
        reconcile_related(note)
        status = note.status
        SessionLocal.commit()
        return status
    except Exception:
        SessionLocal.rollback()
        raise
    finally:
        SessionLocal.remove()


def handle_message(raw: bytes) -> None:
    body = json.loads(raw)
    status = deliver(uuid.UUID(body["tenantId"]), uuid.UUID(body["notificationId"]))
    logger.info("notification %s -> %s", body["notificationId"], status)


def render_document(tenant_id: uuid.UUID, document_id: uuid.UUID) -> str | None:
    """Render one pending document's PDF. Returns the engine used, or None when it was already done."""
    try:
        engine = document_repo.complete_render(tenant_id, document_id)
        SessionLocal.commit()
        return engine
    except Exception:
        SessionLocal.rollback()
        raise
    finally:
        SessionLocal.remove()


def handle_document_message(raw: bytes) -> None:
    body = json.loads(raw)
    engine = render_document(uuid.UUID(body["tenantId"]), uuid.UUID(body["documentId"]))
    logger.info("document %s -> %s", body["documentId"], engine or "already rendered")


def sweep_documents_once(now: datetime | None = None) -> int:
    """Renders every pending document older than the grace period (its message was lost, or the broker was
    down at publish time); returns how many were tried."""
    now = now or datetime.now(timezone.utc)
    try:
        due = [
            (d.tenant_id, d.id)
            for d in Document.query.filter(
                Document.kind == "generated",
                Document.checksum.is_(None),
                Document.bytes_ == 0,
                Document.created_at <= now - timedelta(seconds=SWEEP_GRACE_SECONDS),
            )
            .order_by(Document.created_at)
            .limit(50)
            .all()
        ]
    finally:
        SessionLocal.remove()
    for tenant_id, document_id in due:
        try:
            render_document(tenant_id, document_id)
        except Exception:  # noqa: BLE001 - one bad document must not stop the sweep
            logger.exception("sweep: rendering %s failed", document_id)
    return len(due)


def sweep_once(now: datetime | None = None) -> int:
    """Delivers every due queued notification; returns how many were tried."""
    now = now or datetime.now(timezone.utc)
    try:
        due = [
            (n.tenant_id, n.id)
            for n in Notification.query.filter(
                Notification.status == "queued",
                Notification.next_attempt_at <= now,
                Notification.created_at <= now - timedelta(seconds=SWEEP_GRACE_SECONDS),
            )
            .order_by(Notification.created_at)
            .limit(100)
            .all()
        ]
    finally:
        SessionLocal.remove()
    for tenant_id, notification_id in due:
        try:
            deliver(tenant_id, notification_id)
        except Exception:  # noqa: BLE001 - one bad row must not stop the sweep
            logger.exception("sweep: delivering %s failed", notification_id)
    return len(due)


def _sweeper_loop() -> None:
    while not stop_event.wait(settings.worker_sweep_seconds):
        try:
            n = sweep_once()
            if n:
                logger.info("sweep delivered/retried %d notification(s)", n)
            d = sweep_documents_once()
            if d:
                logger.info("sweep rendered %d document(s)", d)
        except Exception:  # noqa: BLE001
            logger.exception("sweep failed")


def consume_forever(queue: str | None = None, handler=None) -> None:
    queue = queue or settings.notification_queue
    handler = handler or handle_message
    backoff = 1
    while not stop_event.is_set():
        try:
            connection = pika.BlockingConnection(messaging.connection_parameters())
            channel = connection.channel()
            messaging.declare_queues(channel, queue)
            channel.basic_qos(prefetch_count=1)
            logger.info("consuming %s", queue)
            backoff = 1
            for method, _properties, body in channel.consume(queue, inactivity_timeout=1):
                if stop_event.is_set():
                    break
                if method is None:
                    continue
                try:
                    handler(body)
                    channel.basic_ack(method.delivery_tag)
                except Exception:  # noqa: BLE001
                    logger.exception("message rejected to the dead-letter queue: %r", body[:200])
                    channel.basic_nack(method.delivery_tag, requeue=False)
            try:
                channel.cancel()
                connection.close()
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001 - broker down / connection lost: retry with backoff
            logger.warning("broker connection lost (%s); retrying in %ss", exc, backoff)
            stop_event.wait(backoff)
            backoff = min(backoff * 2, 30)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop_event.set())
    threading.Thread(target=_sweeper_loop, name="sweeper", daemon=True).start()
    threading.Thread(target=consume_forever, args=(settings.document_queue, handle_document_message), name="documents", daemon=True).start()
    logger.info("worker started (sweep every %ss)", settings.worker_sweep_seconds)
    consume_forever()
    logger.info("worker stopped")


if __name__ == "__main__":
    main()
