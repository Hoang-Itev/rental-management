import asyncio
import logging

from pydantic import ValidationError

from app.schemas import InvoiceIssued
from app.service import record_invoice_event

QUEUE = "notification.events.q"
ROUTING_KEY = "invoice.issued.v1"
logger = logging.getLogger(__name__)


async def handle_delivery(message, sessions):
    if message.routing_key != ROUTING_KEY:
        # Other event types on this shared queue belong to later phases.
        await message.ack()
        return
    try:
        event = InvoiceIssued.model_validate_json(message.body)
    except ValidationError:
        logger.warning("Rejected invalid InvoiceIssued payload")
        await message.reject(requeue=False)
        return
    try:
        await asyncio.to_thread(record_invoice_event, sessions, event)
    except Exception:
        logger.warning("Could not persist InvoiceIssued, requeueing")
        await asyncio.sleep(2)
        await message.nack(requeue=True)
        return
    await message.ack()
