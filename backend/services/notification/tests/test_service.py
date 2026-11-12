from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app import repository
from app.clients import DeliveryFailure, InvoiceNotIssued
from app.service import record_invoice_event, reset_failed_job, send_next

NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


@pytest.fixture
def delivery(monkeypatch):
    job = SimpleNamespace(
        id=uuid4(), status="PENDING", attempt_count=0, next_attempt_at=None,
        email_type="INVOICE", template_data={
            "tenant_name": "Người thuê", "invoice_code": "INV-A1", "room_code": "A1",
            "period_start": "2026-10-01", "period_end_exclusive": "2026-11-01",
            "total_amount": 1000000, "due_date": "2026-11-05",
        },
    )
    monkeypatch.setattr(repository, "claim_due", lambda *_: job)
    billing, smtp = Mock(), Mock()
    billing.access_link.return_value = "https://example.com/invoice"
    smtp.send.return_value = "message-id"
    settings = SimpleNamespace(notification_retry_seconds=30, notification_max_attempts=2)
    sessions = SimpleNamespace(begin=lambda: nullcontext("db"))
    return job, billing, smtp, lambda: send_next(sessions, billing, smtp, settings, clock=lambda: NOW)


def test_sends_invoice(delivery):
    job, _, smtp, send = delivery
    assert send()
    assert job.status == "SENT" and job.sent_at == NOW
    assert job.provider_message_id == "message-id"
    assert "https://example.com/invoice" in smtp.send.call_args.args[1]
    assert "1,000,000 VND" in smtp.send.call_args.args[1]


def test_smtp_backoff_then_manual_reset(delivery):
    job, _, smtp, send = delivery
    smtp.send.side_effect = DeliveryFailure("SMTP delivery failed")
    assert send() and job.status == "PENDING"
    assert job.next_attempt_at == NOW + timedelta(seconds=30)
    assert send() and job.status == "FAILED"
    assert job.next_attempt_at is None
    assert reset_failed_job(job) and job.attempt_count == 0
    assert job.last_error is None
    assert not reset_failed_job(job)


def test_skip_if_invoice_no_longer_issued(delivery):
    job, billing, smtp, send = delivery
    billing.access_link.side_effect = InvoiceNotIssued
    assert send() and job.status == "SKIPPED"
    smtp.send.assert_not_called()


def test_no_pending_job(delivery, monkeypatch):
    monkeypatch.setattr(repository, "claim_due", lambda *_: None)
    assert not delivery[-1]()


def test_event_uses_repository_transaction(monkeypatch):
    insert = Mock()
    monkeypatch.setattr(repository, "insert_once", insert)
    event = SimpleNamespace(data=SimpleNamespace(invoice_code="INV-1"))
    record_invoice_event(SimpleNamespace(begin=lambda: nullcontext("db")), event)
    insert.assert_called_once_with("db", event, "Hóa đơn INV-1")


def test_payment_receipt_does_not_request_invoice_link(delivery):
    job, billing, smtp, send = delivery
    job.email_type = "PAYMENT_RECEIPT"
    job.template_data.update(paid_amount=1000000, provider_transaction_id="1234")
    assert send() and job.status == "SENT"
    billing.access_link.assert_not_called()
    assert "1234" in smtp.send.call_args.args[1]


def test_payment_event_creates_receipt_job(monkeypatch):
    from app.service import record_payment_event

    insert = Mock()
    monkeypatch.setattr(repository, "insert_once", insert)
    event = SimpleNamespace(data=SimpleNamespace(invoice_code="INV-1"))
    record_payment_event(SimpleNamespace(begin=lambda: nullcontext("db")), event)
    insert.assert_called_once_with("db", event, "Biên nhận INV-1", email_type="PAYMENT_RECEIPT")
