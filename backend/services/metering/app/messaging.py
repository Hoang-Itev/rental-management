"""Consume RoomCreated from durable RabbitMQ queue with manual ACK and retry/DLQ.

ACK only after PostgreSQL commit, or after the broker confirms safe transfer to
TTL retry/DLQ. If republishing fails, reject/requeue the original message.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.service import MeteringService

logger = logging.getLogger(__name__)
QUEUE = "metering.events.q"
RETRY_DELAYS = (10, 60, 300)


async def transfer(channel, queue_name: str, body: bytes, headers: dict) -> None:
    """Broker-confirmed transfer to a durable retry queue or DLQ."""
    import aio_pika

    msg = aio_pika.Message(
        body=body, content_type="application/json",
        headers=headers, delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    confirmation = await asyncio.wait_for(
        channel.default_exchange.publish(msg, routing_key=queue_name, mandatory=True),
        timeout=10,
    )
    if confirmation is None or type(confirmation).__name__ != "Ack":
        raise RuntimeError("retry/DLQ transfer not confirmed")


async def process_delivery(message, channel, sessions: sessionmaker[Session]) -> str:
    """Process a delivery; return processed/duplicate/retry/deadletter for diagnostics."""
    try:
        envelope = json.loads(message.body)
        if not isinstance(envelope, dict):
            raise ValueError("event body must be an object")
        if envelope.get("event_type") != "RoomCreated":
            raise ValueError("event type not supported in P03")
        # Validation is outside database TX, so malformed events never get
        # recorded as processed and can be quarantined without retry loops.
        from app.service import RoomCreatedEnvelope
        RoomCreatedEnvelope.model_validate(envelope)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, ValidationError) as exc:
        try:
            await transfer(channel, QUEUE + ".dlq", message.body,
                           {**(message.headers or {}), "x-p03-error": "invalid-envelope"})
        except Exception:
            await message.reject(requeue=True)
            raise
        await message.ack()
        logger.warning("Quarantined invalid/unsupported Metering event (%s)", type(exc).__name__)
        return "deadletter"

    try:
        with sessions() as session:
            applied = MeteringService(session).process_room_created(envelope)
    except Exception as exc:
        try:
            retry = int((message.headers or {}).get("x-p03-retry", 0))
        except (TypeError, ValueError):
            retry = 0
        dest = QUEUE + ".dlq" if retry >= len(RETRY_DELAYS) else (
            QUEUE + ".retry." + str(RETRY_DELAYS[retry]) + "s"
        )
        new_headers = {**(message.headers or {}), "x-p03-retry": retry + 1,
                       "x-p03-error": type(exc).__name__[:80]}
        try:
            await transfer(channel, dest, message.body, new_headers)
        except Exception:
            # Original has not been ACKed, so it can be redelivered.
            await message.reject(requeue=True)
            raise
        await message.ack()
        logger.warning("Metering event handling failed (%s), queued to %s", type(exc).__name__, dest)
        return "deadletter" if retry >= len(RETRY_DELAYS) else "retry"

    # ACK only after process_room_created commits its database transaction.
    await message.ack()
    return "processed" if applied else "duplicate"
