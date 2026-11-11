"""Dedicated Tenant outbox worker; not part of the HTTP process."""
import asyncio
import logging
import os
import signal
from app.db import get_sessionmaker
from app.messaging import RabbitPublisher,publish_pending

logging.basicConfig(level='INFO')
logger=logging.getLogger('tenant.outbox')

async def run():
    import aio_pika
    stop=asyncio.Event()
    loop=asyncio.get_running_loop()
    for sig in (signal.SIGTERM,signal.SIGINT):
        try:loop.add_signal_handler(sig,stop.set)
        except NotImplementedError:pass
    while not stop.is_set():
        try:
            conn=await aio_pika.connect_robust(os.environ['RABBITMQ_URL'],timeout=8)
            async with conn:
                channel=await conn.channel(publisher_confirms=True,on_return_raises=True)
                publisher=RabbitPublisher(channel)
                await publisher.start()
                while not stop.is_set():
                    count,failed=await publish_pending(get_sessionmaker(),publisher)
                    try:await asyncio.wait_for(stop.wait(),timeout=3 if failed else (1 if count==0 else .1))
                    except asyncio.TimeoutError:pass
        except asyncio.CancelledError:raise
        except Exception as exc:
            logger.warning('Tenant outbox worker reconnect (%s)',type(exc).__name__)
            try:await asyncio.wait_for(stop.wait(),timeout=5)
            except asyncio.TimeoutError:pass

if __name__=='__main__':asyncio.run(run())
