import asyncio
import logging

from pydantic import ValidationError

from app.schemas import ContractExpiring, InvoiceIssued, InvoiceReminderRequested, PaymentSucceeded
from app.service import record_expiring_event, record_invoice_event, record_payment_event, record_reminder_event

QUEUE = "notification.events.q"
HANDLERS = {
    "invoice.issued.v1": (InvoiceIssued, record_invoice_event),
    "payment.succeeded.v1": (PaymentSucceeded, record_payment_event),
    "invoice.reminder_requested.v1": (InvoiceReminderRequested, record_reminder_event),
    "contract.expiring.v1": (ContractExpiring, record_expiring_event),
}
logger = logging.getLogger(__name__)


async def handle_delivery(message, sessions, owner_email="owner@example.com"):
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
        args = (owner_email,) if schema is ContractExpiring else ()
        await asyncio.to_thread(record, sessions, event, *args)
    except Exception:
        logger.warning("Could not persist notification event, requeueing")
        await asyncio.sleep(2)
        await message.nack(requeue=True)
        return
    await message.ack()
