import asyncio
import logging

from pydantic import ValidationError

from app.schemas import InvoiceIssued, PaymentSucceeded
from app.service import record_invoice_event, record_payment_event

QUEUE = "notification.events.q"
HANDLERS = {
    "invoice.issued.v1": (InvoiceIssued, record_invoice_event),
    "payment.succeeded.v1": (PaymentSucceeded, record_payment_event),
}
logger = logging.getLogger(__name__)


async def handle_delivery(message, sessions):
    handler = HANDLERS.get(message.routing_key)
    if handler is None:
        # Other event types on this shared queue belong to later phases.
        await message.ack()
        return
    schema, record = handler
    try:
        event = schema.model_validate_json(message.body)
    except ValidationError:
        logger.warning("Rejected invalid notification event")
        await message.reject(requeue=False)
        return
    try:
        await asyncio.to_thread(record, sessions, event)
    except Exception:
        logger.warning("Could not persist notification event, requeueing")
        await asyncio.sleep(2)
        await message.nack(requeue=True)
        return
    await message.ack()
