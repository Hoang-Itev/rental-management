"""Transactional outbox publisher: ack at broker before marking the row published.

Delivery is at-least-once; duplicate deliveries are expected and handled by event consumers.
Workers use SELECT FOR UPDATE SKIP LOCKED to avoid publishing the same pending
row concurrently. A process crash between broker confirm and DB commit may
still republish the event, intentionally.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from app import repository as repo

logger = logging.getLogger(__name__)


class Publisher(Protocol):
    async def publish(self, body: dict) -> None: ...


async def publish_pending(
    sessions: sessionmaker[Session], sender: Publisher, *, limit: int = 20,
) -> tuple[int, bool]:
    """Publish up to limit events. Returns (confirmed_count, had_failure).

    A transaction is held across broker confirmation. This is deliberate to
    ensure a confirmed publish precedes published_at, and is bounded by the
    broker timeout. On publish failure, the unmarked row remains retryable.
    """
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    published = 0
    for _ in range(limit):
        with sessions() as session:
            with session.begin():
                row = repo.claim_outbox(session)
                if row is None:
                    return published, False
                try:
                    await sender.publish(row.payload)
                except Exception as exc:
                    row.attempts += 1
                    # Do not persist broker URL, credentials, or exception text.
                    row.last_error = "Publish failed: " + type(exc).__name__
                    logger.warning("Billing event publish failed for outbox ID %s (%s)", row.id, type(exc).__name__)
                    return published, True
                row.published_at = datetime.now(timezone.utc)
                row.attempts += 1
                row.last_error = None
                published += 1
    return published, False


class RabbitPublisher:
    """aio-pika mandatory + durable + publisher confirms; robust connection elsewhere."""

    def __init__(self, channel):
        self.channel = channel
        self.exchange = None

    async def start(self) -> None:
        import aio_pika
        self.exchange = await self.channel.declare_exchange(
            "rental.domain.v1", type=aio_pika.ExchangeType.TOPIC, durable=True,
        )

    async def publish(self, body: dict) -> None:
        import aio_pika
        if self.exchange is None:
            raise RuntimeError("publisher not started")
        msg = aio_pika.Message(
            body=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            content_type="application/json",
            message_id=str(body["event_id"]),
            correlation_id=str(body["correlation_id"]),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        confirmation = await asyncio.wait_for(
            self.exchange.publish(msg, routing_key={
                "InvoiceIssued": "invoice.issued.v1",
                "PaymentSucceeded": "payment.succeeded.v1",
            }[body["event_type"]], mandatory=True),
            timeout=10,
        )
        # publisher_confirms=True produces a Basic.Ack when the broker confirms.
        if confirmation is None or type(confirmation).__name__ != "Ack":
            raise RuntimeError("broker did not confirm Billing event")
