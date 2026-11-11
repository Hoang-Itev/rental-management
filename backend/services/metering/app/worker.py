"""Dedicated RabbitMQ consumer; never start this as a FastAPI background task."""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from app.db import get_sessionmaker
from app.messaging import QUEUE, process_delivery

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("metering.consumer")


async def run() -> None:
    import aio_pika

    url = os.environ["RABBITMQ_URL"]
    sessions = get_sessionmaker()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    while not stop.is_set():
        try:
            connection = await aio_pika.connect_robust(url, timeout=8)
            async with connection:
                channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
                await channel.set_qos(prefetch_count=8)
                queue = await channel.declare_queue(QUEUE, durable=True)
                logger.info("Metering consuming durable queue %s", QUEUE)
                async with queue.iterator() as iterator:
                    async for message in iterator:
                        if stop.is_set():
                            # Unacked delivery is returned when the channel closes.
                            break
                        await process_delivery(message, channel, sessions)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Metering consumer reconnecting (%s)", type(exc).__name__)
            try:
                await asyncio.wait_for(stop.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass


if __name__ == "__main__":
    asyncio.run(run())
