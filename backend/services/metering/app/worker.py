"""Run one isolated AMQP consumer per queue.

python -m app.worker           # P03/P05 domain events
python -m app.worker telemetry # P06 MQTT telemetry bridge
"""
from __future__ import annotations
import asyncio
import logging
import os
import signal
import sys
from app.db import get_sessionmaker
from app.messaging import QUEUE, TELEMETRY_QUEUE, process_delivery, process_telemetry_delivery

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger('metering.consumer')

async def run(*, telemetry: bool = False) -> None:
    import aio_pika
    url = os.environ['RABBITMQ_URL']
    sessions = get_sessionmaker()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, stop.set)
        except NotImplementedError: pass
    queue_name = TELEMETRY_QUEUE if telemetry else QUEUE
    handler = process_telemetry_delivery if telemetry else process_delivery
    while not stop.is_set():
        try:
            connection = await aio_pika.connect_robust(url, timeout=8)
            async with connection:
                channel = await connection.channel(publisher_confirms=True,
                                                  on_return_raises=True)
                await channel.set_qos(prefetch_count=8)
                queue = await channel.declare_queue(queue_name, durable=True)
                logger.info('Metering consuming %s', queue_name)
                async with queue.iterator() as it:
                    async for message in it:
                        if stop.is_set(): break
                        await handler(message, channel, sessions)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning('%s consumer reconnect after %s', queue_name, type(exc).__name__)
            try: await asyncio.wait_for(stop.wait(), timeout=5)
            except asyncio.TimeoutError: pass

if __name__ == '__main__':
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] != 'telemetry'):
        raise SystemExit('Usage: python -m app.worker [telemetry]')
    asyncio.run(run(telemetry=len(sys.argv) == 2))
