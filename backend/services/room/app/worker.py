"""Run via `python -m app.worker`; separate from the HTTP server."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from app.db import get_sessionmaker
from app.messaging import RabbitPublisher, publish_pending

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("room.outbox")


async def run() -> None:
    import aio_pika

    url = os.environ["RABBITMQ_URL"]
    sessions = get_sessionmaker()
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except NotImplementedError:
            pass

    while not stopping.is_set():
        try:
            connection = await aio_pika.connect_robust(url, timeout=8)
            async with connection:
                channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
                sender = RabbitPublisher(channel)
                await sender.start()
                logger.info("Room outbox publisher connected")
                while not stopping.is_set():
                    count, failed = await publish_pending(sessions, sender)
                    if failed:
                        await asyncio.sleep(3)
                    elif count == 0:
                        await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Outbox worker reconnecting after %s", type(exc).__name__)
            try:
                await asyncio.wait_for(stopping.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass




async def consume():
    import aio_pika
    from app.consumer import QUEUE,delivery
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
                await channel.set_qos(prefetch_count=8)
                queue=await channel.declare_queue(QUEUE,durable=True)
                async with queue.iterator() as iterator:
                    async for message in iterator:
                        if stop.is_set():break
                        await delivery(message,channel,get_sessionmaker())
        except asyncio.CancelledError:raise
        except Exception as exc:
            logger.warning('Room consumer reconnect (%s)',type(exc).__name__)
            try:await asyncio.wait_for(stop.wait(),timeout=5)
            except asyncio.TimeoutError:pass

if __name__ == "__main__":
    asyncio.run(consume() if len(sys.argv)>1 and sys.argv[1]=="consume" else run())
