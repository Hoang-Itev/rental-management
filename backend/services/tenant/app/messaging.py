"""Tenant transactional outbox publisher with RabbitMQ publisher confirms."""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone
from sqlalchemy import select, cast, DateTime, func
from sqlalchemy.orm import sessionmaker, Session
from app import models as m

logger=logging.getLogger(__name__)
ROUTING={'ContractStarted':'contract.started.v1','ContractEnded':'contract.ended.v1','ContractExpiring':'contract.expiring.v1'}


async def publish_pending(sessions: sessionmaker[Session], publisher, *, limit=20):
    published=0
    for _ in range(limit):
        with sessions() as db:
            with db.begin():
                # PostgreSQL evaluates timezone-aware effective_at, so future
                # termination records CANNOT publish prematurely.
                query=(select(m.OutboxEvent)
                    .where(m.OutboxEvent.event_type.in_(tuple(ROUTING)),
                           m.OutboxEvent.published_at.is_(None),
                           cast(m.OutboxEvent.payload['effective_at'].as_string(), DateTime(timezone=True)) <= func.now())
                    .order_by(m.OutboxEvent.created_at,m.OutboxEvent.id)
                    .limit(1).with_for_update(skip_locked=True))
                row=db.scalars(query).first()
                if row is None:
                    return published,False
                try:
                    await publisher.publish(row.payload)
                except Exception as exc:
                    row.attempts+=1
                    row.last_error='Publish failed: '+type(exc).__name__
                    logger.warning('Tenant outbox %s retry after %s',row.id,type(exc).__name__)
                    return published,True
                row.published_at=datetime.now(timezone.utc)
                row.last_error=None
                row.attempts+=1
                published+=1
    return published,False


class RabbitPublisher:
    def __init__(self, channel):
        self.channel=channel
        self.exchange=None

    async def start(self):
        import aio_pika
        self.exchange=await self.channel.declare_exchange('rental.domain.v1',type=aio_pika.ExchangeType.TOPIC,durable=True)

    async def publish(self,body):
        import aio_pika
        if self.exchange is None:
            raise RuntimeError('Publisher is not initialized')
        msg=aio_pika.Message(body=json.dumps(body,separators=(',',':')).encode(),
            content_type='application/json',message_id=body['event_id'],
            correlation_id=body['correlation_id'],delivery_mode=aio_pika.DeliveryMode.PERSISTENT)
        ack=await asyncio.wait_for(self.exchange.publish(msg,ROUTING[body['event_type']],mandatory=True),timeout=10)
        if ack is None or type(ack).__name__!='Ack':
            raise RuntimeError('RabbitMQ publish was not confirmed')
