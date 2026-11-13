"""SePay checkout and authenticated IPN transitions using the existing Billing database.

One PENDING attempt per invoice across all providers. No redirect can mark
an invoice paid; only validated IPN can do so, under a PostgreSQL row lock.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select, text

from app import models as m, repository as repo
from app.payment import PaymentService, utcnow
from app.schemas import SePayCheckoutSession, SePayIPN
from app.service import LinkDenied, hash_link_token


class SePayPaymentService:
    def __init__(self, sessions, gateway):
        self.sessions = sessions
        self.gateway = gateway

    def _view(self, invoice, attempt, reused: bool) -> SePayCheckoutSession:
        success = attempt.status == "SUCCESS"
        return SePayCheckoutSession(
            payment_attempt_id=attempt.id,
            status="SUCCESS" if success else "PENDING",
            reused_pending_attempt=reused,
            checkout_status="PAID" if success else "READY",
            action_url=None if success else self.gateway.action_url,
            method="POST",
            fields=None if success else self.gateway.form(invoice, attempt),
        )

    def checkout(self, token: str, key: str | None = None) -> SePayCheckoutSession:
        if not self.gateway.enabled:
            raise LinkDenied(503, "SEPAY_UNAVAILABLE")
        with self.sessions.begin() as db:
            link = repo.usable_invoice_link(db, hash_link_token(token), utcnow())
            if link is None:
                raise LinkDenied(404, "LINK_NOT_FOUND")
            invoice = db.get(m.Invoice, link.invoice_id, with_for_update=True)
            if invoice.status == "PAID":
                success = repo.payment_attempt(db, invoice.id, status="SUCCESS")
                if success is not None and success.provider == "SEPAY":
                    return self._view(invoice, success, reused=False)
                raise LinkDenied(409, "INVOICE_ALREADY_PAID")
            if invoice.status != "ISSUED":
                raise LinkDenied(409, "INVOICE_NOT_PAYABLE")
            if invoice.total_amount <= 0:
                raise LinkDenied(422, "SEPAY_AMOUNT_OUT_OF_RANGE")

            request_id = (uuid5(NAMESPACE_URL, f"rental:sepay:{invoice.id}:{key}").hex
                          if key else uuid4().hex)
            previous = repo.payment_attempt(db, invoice.id, request_id=request_id)
            if previous is not None and previous.status != "PENDING":
                raise LinkDenied(409, "PAYMENT_ATTEMPT_CLOSED")
            pending = repo.payment_attempt(db, invoice.id, status="PENDING")
            attempt = previous or pending
            if attempt is not None:
                if attempt.provider != "SEPAY":
                    raise LinkDenied(409, "PAYMENT_PROVIDER_CONFLICT")
                if attempt.amount != invoice.total_amount:
                    raise LinkDenied(409, "PAYMENT_AMOUNT_CHANGED")
                return self._view(invoice, attempt, reused=True)

            attempt = m.PaymentAttempt(
                id=uuid4(), invoice_id=invoice.id, provider="SEPAY",
                order_id="SEP-" + uuid4().hex, request_id=request_id,
                amount=invoice.total_amount, status="PENDING",
            )
            db.add(attempt)
            db.flush()
            return self._view(invoice, attempt, reused=False)

    def receive_ipn(self, ipn: SePayIPN, candidate_secret: str | None) -> str:
        if not self.gateway.verify_ipn(candidate_secret):
            raise LinkDenied(401, "SEPAY_INVALID_IPN_SECRET")

        fingerprint = hashlib.sha256(
            json.dumps(ipn.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        attempt_name = ipn.order.order_invoice_number
        result = "UNKNOWN_ORDER"
        with self.sessions.begin() as db:
            pair = db.execute(select(m.PaymentAttempt.id, m.PaymentAttempt.invoice_id).where(
                m.PaymentAttempt.order_id == attempt_name,
                m.PaymentAttempt.provider == "SEPAY",
            )).one_or_none()
            attempt_id = pair[0] if pair else None
            if pair is not None:
                invoice = db.get(m.Invoice, pair[1], with_for_update=True)
                attempt = db.get(m.PaymentAttempt, pair[0], with_for_update=True)
                valid_currency = (ipn.order.order_currency == "VND"
                                  and ipn.transaction.transaction_currency == "VND")
                valid_amount = (ipn.order.order_amount == attempt.amount == invoice.total_amount
                                and ipn.transaction.transaction_amount == attempt.amount)
                if not valid_currency or not valid_amount:
                    result = "AMOUNT_MISMATCH"
                elif ipn.notification_type == "TRANSACTION_VOID":
                    if attempt.status == "PENDING" and invoice.status == "ISSUED":
                        attempt.status = "FAILED"
                        attempt.result_code = "TRANSACTION_VOID"
                        result = "PROCESSED"
                    else:
                        # A void after a confirmed payment is a manual accounting
                        # exception: never silently change an immutable PAID invoice.
                        result = "RECONCILIATION_REQUIRED" if invoice.status == "PAID" else "DUPLICATE"
                elif (ipn.order.order_status != "CAPTURED"
                      or ipn.transaction.transaction_status != "APPROVED"
                      or ipn.transaction.transaction_type != "PAYMENT"):
                    result = "RECONCILIATION_REQUIRED"
                elif (attempt.status == "SUCCESS" and invoice.status == "PAID"
                      and attempt.provider_transaction_id == ipn.transaction.transaction_id):
                    result = "DUPLICATE"
                elif attempt.status != "PENDING" or invoice.status != "ISSUED":
                    result = "RECONCILIATION_REQUIRED"
                else:
                    # Serialize reuse of a provider transaction across different invoices.
                    transaction_id = ipn.transaction.transaction_id
                    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                               {"key": f"sepay-transaction:{transaction_id}"})
                    exists = db.scalar(select(m.PaymentAttempt.id).where(
                        m.PaymentAttempt.provider == "SEPAY",
                        m.PaymentAttempt.provider_transaction_id == transaction_id,
                        m.PaymentAttempt.status == "SUCCESS",
                        m.PaymentAttempt.id != attempt.id,
                    ).limit(1))
                    if exists:
                        result = "RECONCILIATION_REQUIRED"
                    else:
                        PaymentService._mark_paid(db, invoice, attempt, transaction_id)
                        result = "PROCESSED"

            db.add(m.PaymentWebhookReceipt(
                payment_attempt_id=attempt_id, order_id=attempt_name,
                payload_fingerprint=fingerprint, signature_valid=True,
                processing_result=result, processed_at=utcnow(),
            ))

        if result == "UNKNOWN_ORDER":
            raise LinkDenied(404, result)
        if result == "AMOUNT_MISMATCH":
            raise LinkDenied(409, result)
        if result == "RECONCILIATION_REQUIRED":
            raise LinkDenied(409, result)
        return result
