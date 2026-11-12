"""Run via `python -m app.worker`; separate from the HTTP server."""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from app.db import get_sessionmaker
from app.messaging import RabbitPublisher, publish_pending

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("billing.outbox")


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
                logger.info("Billing outbox publisher connected")
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




if __name__ == "__main__":
    asyncio.run(run())
