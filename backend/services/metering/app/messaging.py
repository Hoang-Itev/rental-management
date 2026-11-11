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
        # Contract events share the existing durable Metering queue.
        # Unknown/malformed envelopes remain quarantined.
        from app.service import RoomCreatedEnvelope
        from app.lifecycle import ContractEnvelope
        if envelope.get('event_type') == 'RoomCreated':
            RoomCreatedEnvelope.model_validate(envelope)
        elif envelope.get('event_type') in ('ContractStarted','ContractEnded'):
            ContractEnvelope.model_validate(envelope)
        else:
            raise ValueError('unknown Metering event_type')
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
            service=MeteringService(session)
            applied = (service.process_room_created(envelope) if envelope['event_type']=='RoomCreated'
                       else service.process_contract_event(envelope))
    except Exception as exc:
        from app.lifecycle import FutureEvent
        future=isinstance(exc, FutureEvent)
        try:
            retry = int((message.headers or {}).get("x-p03-retry", 0))
        except (TypeError, ValueError):
            retry = 0
        # Future effective_at is a scheduling condition, not a failure.
        dest = (QUEUE + '.retry.300s' if future else
                (QUEUE + ".dlq" if retry >= len(RETRY_DELAYS) else
                 QUEUE + ".retry." + str(RETRY_DELAYS[retry]) + "s"))
        new_headers = {**(message.headers or {}),
                       "x-p03-error": type(exc).__name__[:80]}
        if not future:
            new_headers['x-p03-retry']=retry + 1
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

TELEMETRY_QUEUE = 'metering.telemetry.q'

async def process_telemetry_delivery(message, channel, sessions: sessionmaker[Session]) -> str:
    """Handle MQTT->Rabbit AMQP telemetry with durable manual ACK/retry/DLQ.

    Retry round-tripping through default-exchange TTL queues rewrites the
    routing key; x-p06-original-key preserves the MQTT topic for validation.
    """
    from app import schemas as s
    from app.telemetry import InvalidTelemetry
    headers = dict(message.headers or {})
    original_key = headers.get('x-p06-original-key') or message.routing_key
    try:
        body = json.loads(message.body)
        if not isinstance(body, dict):
            raise ValueError('JSON object required')
        sample = s.Telemetry.model_validate(body)
        if original_key != f'meters.{sample.meter_id}.reading':
            raise InvalidTelemetry('MQTT routing key must match meter_id')
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        try:
            await transfer(channel, TELEMETRY_QUEUE + '.dlq', message.body,
                           {**headers, 'x-p06-error': 'invalid-telemetry',
                            'x-p06-original-key': str(original_key)[:180]})
        except Exception:
            await message.reject(requeue=True)
            raise
        await message.ack()
        logger.warning('Quarantined invalid MQTT telemetry (%s)', type(exc).__name__)
        return 'deadletter'

    try:
        with sessions() as session:
            result = MeteringService(session).record_telemetry(body,
                routing_key=str(original_key))
    except InvalidTelemetry as exc:
        try:
            await transfer(channel, TELEMETRY_QUEUE + '.dlq', message.body,
                           {**headers, 'x-p06-error': type(exc).__name__[:80],
                            'x-p06-original-key': str(original_key)[:180]})
        except Exception:
            await message.reject(requeue=True)
            raise
        await message.ack()
        return 'deadletter'
    except Exception as exc:
        try:
            attempt = max(0, int(headers.get('x-p06-retry', 0)))
        except (ValueError, TypeError):
            attempt = 0
        dest = (TELEMETRY_QUEUE + '.dlq' if attempt >= len(RETRY_DELAYS) else
                f'{TELEMETRY_QUEUE}.retry.{RETRY_DELAYS[attempt]}s')
        try:
            await transfer(channel, dest, message.body, {
                **headers, 'x-p06-retry': attempt + 1,
                'x-p06-error': type(exc).__name__[:80],
                'x-p06-original-key': str(original_key)[:180],
            })
        except Exception:
            await message.reject(requeue=True)
            raise
        await message.ack()
        logger.warning('MQTT DB failure (%s) transferred to %s', type(exc).__name__, dest)
        return 'deadletter' if attempt >= len(RETRY_DELAYS) else 'retry'
    await message.ack()
    return result
