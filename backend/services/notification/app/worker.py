import asyncio
import logging
import os

import aio_pika
import httpx

from app.clients import BillingClient, SmtpClient
from app.config import get_settings
from app.db import get_sessionmaker
from app.messaging import QUEUE, handle_delivery
from app.service import send_next

logger = logging.getLogger(__name__)


async def consume(sessions):
    while True:
        try:
            connection = await aio_pika.connect_robust(os.environ["RABBITMQ_URL"], timeout=8)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=1)
                queue = await channel.get_queue(QUEUE)
                async with queue.iterator() as messages:
                    async for message in messages:
                        await handle_delivery(message, sessions)
        except Exception as exc:
            logger.warning("Notification consumer reconnecting (%s)", type(exc).__name__)
            await asyncio.sleep(5)


async def dispatch(sessions, settings):
    with httpx.Client(timeout=settings.notification_timeout_seconds, trust_env=False) as http:
        billing, smtp = BillingClient(http, settings), SmtpClient(settings)
        while True:
            try:
                if await asyncio.to_thread(send_next, sessions, billing, smtp, settings):
                    continue
            except Exception as exc:
                logger.warning("Notification dispatcher failed (%s)", type(exc).__name__)
            await asyncio.sleep(settings.notification_poll_seconds)


async def run():
    sessions = get_sessionmaker()
    async with asyncio.TaskGroup() as group:
        group.create_task(consume(sessions))
        group.create_task(dispatch(sessions, get_settings()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
