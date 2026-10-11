"""RabbitMQ publishing.

The API never delivers slow side effects itself when ASYNC_NOTIFICATIONS is on:
it records the work in Postgres (a `queued` notification row) inside the
request's own transaction, and only AFTER that transaction commits publishes a
small message telling the worker which row to pick up. Two consequences worth
knowing:

* A rolled-back request publishes nothing, and a published message always
  points at a committed row (the worker can never race ahead of the commit).
* The message is an optimisation, not the source of truth. If the broker is
  down when we publish, the failure is logged and swallowed - the row is still
  `queued` in the database and the worker's periodic sweep delivers it.

`publish_after_commit` is what call sites use; `set_broker` swaps in a fake in
tests. Publishing is a short blocking call on the request thread, bounded by
the connection timeouts below.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Protocol

import pika
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import session

logger = logging.getLogger("app.messaging")

_PENDING_KEY = "pending_messages"


class Broker(Protocol):
    def publish(self, queue: str, body: dict) -> None: ...

    def healthy(self) -> bool: ...


def dead_letter_queue(queue: str) -> str:
    return f"{queue}.dead"


def declare_queues(channel, queue: str) -> None:
    """Idempotent - publisher and consumer both call it, and RabbitMQ requires
    the two declarations to carry identical arguments. Messages the worker
    rejects (unparseable, or crashing the handler) go to `<queue>.dead`
    instead of being redelivered forever."""
    channel.queue_declare(queue=dead_letter_queue(queue), durable=True)
    channel.queue_declare(
        queue=queue,
        durable=True,
        arguments={"x-dead-letter-exchange": "", "x-dead-letter-routing-key": dead_letter_queue(queue)},
    )


def connection_parameters() -> pika.URLParameters:
    params = pika.URLParameters(settings.rabbitmq_url)
    params.socket_timeout = 3
    params.blocked_connection_timeout = 5
    params.heartbeat = 30
    return params


class PikaBroker:
    """One lazily-opened, lock-guarded connection per process; a failed publish
    drops the connection and retries once on a fresh one."""

    def __init__(self) -> None:
        self._connection: pika.BlockingConnection | None = None
        self._channel = None
        self._declared: set[str] = set()
        self._lock = threading.Lock()

    def _open(self, queue: str):
        if self._connection is None or self._connection.is_closed or self._channel is None or self._channel.is_closed:
            self._connection = pika.BlockingConnection(connection_parameters())
            self._channel = self._connection.channel()
            self._declared = set()
        if queue not in self._declared:
            declare_queues(self._channel, queue)
            self._declared.add(queue)
        return self._channel

    def _drop(self) -> None:
        try:
            if self._connection is not None and not self._connection.is_closed:
                self._connection.close()
        except Exception:  # noqa: BLE001
            pass
        self._connection = None
        self._channel = None

    def publish(self, queue: str, body: dict) -> None:
        payload = json.dumps(body).encode()
        with self._lock:
            for attempt in (1, 2):
                try:
                    self._open(queue).basic_publish(
                        exchange="",
                        routing_key=queue,
                        body=payload,
                        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
                    )
                    return
                except Exception:
                    self._drop()
                    if attempt == 2:
                        raise

    def healthy(self) -> bool:
        try:
            connection = pika.BlockingConnection(connection_parameters())
            connection.close()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("RabbitMQ health check failed: %s", exc)
            return False


_broker: Broker | None = None


def get_broker() -> Broker:
    global _broker
    if _broker is None:
        _broker = PikaBroker()
    return _broker


def set_broker(broker: Broker | None) -> None:
    global _broker
    _broker = broker


def publish_after_commit(queue: str, body: dict) -> None:
    """Queue a message to be published once the CURRENT session's transaction
    commits (dropped if it rolls back)."""
    session.info.setdefault(_PENDING_KEY, []).append((queue, body))


def _flush_pending(db_session: Session) -> None:
    pending = db_session.info.pop(_PENDING_KEY, [])
    for queue, body in pending:
        try:
            get_broker().publish(queue, body)
        except Exception:  # noqa: BLE001 - the queued row is the source of truth; the worker's sweep will find it
            logger.exception("Could not publish to %s (the worker's sweep will pick the row up)", queue)


@event.listens_for(Session, "after_commit")
def _after_commit(db_session: Session) -> None:
    _flush_pending(db_session)


@event.listens_for(Session, "after_rollback")
def _after_rollback(db_session: Session) -> None:
    db_session.info.pop(_PENDING_KEY, None)
