"""Contract events on Room queue, manual ACK after DB commit; TTL retry/DLQ."""
from __future__ import annotations
import asyncio
import json
import logging
from pydantic import ValidationError
from app.lifecycle import ContractEnvelope, FutureEvent, apply_contract_event

logger=logging.getLogger(__name__)
QUEUE='room.events.q'
RETRIES=(10,60,300)


async def transfer(channel, destination, body, headers):
    import aio_pika
    msg=aio_pika.Message(body=body,headers=headers,content_type='application/json',
                         delivery_mode=aio_pika.DeliveryMode.PERSISTENT)
    ack=await asyncio.wait_for(channel.default_exchange.publish(msg,routing_key=destination,mandatory=True),timeout=10)
    if ack is None or type(ack).__name__!='Ack':
        raise RuntimeError('Retry/DLQ publish not confirmed')


async def delivery(message, channel, sessions):
    try:
        raw=json.loads(message.body)
        ContractEnvelope.model_validate(raw)
    except (ValueError,TypeError,ValidationError):
        try:
            await transfer(channel,QUEUE+'.dlq',message.body,{**(message.headers or {}),'x-p05-error':'invalid-envelope'})
        except Exception:
            await message.reject(requeue=True)
            raise
        await message.ack()
        return 'deadletter'
    try:
        with sessions() as db:
            result=apply_contract_event(db,raw)
    except Exception as exc:
        future=isinstance(exc,FutureEvent)
        retry=int((message.headers or {}).get('x-p05-retry',0))
        # Future events have an unlimited defer cycle; do not DLQ merely for time.
        dest=QUEUE+'.retry.300s' if future else (QUEUE+'.dlq' if retry>=len(RETRIES) else QUEUE+f'.retry.{RETRIES[retry]}s')
        headers={**(message.headers or {}),'x-p05-error':type(exc).__name__[:60]}
        if not future:
            headers['x-p05-retry']=retry+1
        try:await transfer(channel,dest,message.body,headers)
        except Exception:
            await message.reject(requeue=True)
            raise
        await message.ack()
        logger.warning('Room event deferred (%s)',type(exc).__name__)
        return 'deferred' if future else 'retry'
    await message.ack()
    return result
