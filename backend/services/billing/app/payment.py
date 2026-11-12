"""Payment state transitions shared by checkout, IPN and reconciliation."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select, text, update

from app import models as m, repository as repo
from app.momo import FINAL_FAILURES, MomoUnavailable
from app.schemas import MomoPaymentSession
from app.service import LinkDenied, hash_link_token

CREATE_REJECTIONS = {20, 21, 22}
RECONCILIATION = "RECONCILIATION_REQUIRED"


def utcnow():
    return datetime.now(timezone.utc)


class PaymentService:
    def __init__(self, sessions, momo):
        self.sessions = sessions
        self.momo = momo

    @staticmethod
    def view(attempt, *, reused):
        return MomoPaymentSession(
            payment_attempt_id=attempt.id, status=attempt.status, reused_pending_attempt=reused,
            pay_url=attempt.pay_url if attempt.status == "PENDING" else None,
            expires_at=attempt.expires_at,
        )

    def checkout(self, token, key):
        if not self.momo.enabled:
            raise LinkDenied(503, "MOMO_UNAVAILABLE")
        with self.sessions.begin() as db:
            link = repo.usable_invoice_link(db, hash_link_token(token), utcnow())
            if link is None:
                raise LinkDenied(404, "LINK_NOT_FOUND")
            invoice = db.get(m.Invoice, link.invoice_id, with_for_update=True)
            if invoice.status == "PAID":
                success = repo.payment_attempt(db, invoice.id, status="SUCCESS")
                if success is not None:
                    return self.view(success, reused=False)
            if invoice.status != "ISSUED":
                raise LinkDenied(409, "INVOICE_NOT_PAYABLE")
            if not 10000 <= invoice.total_amount <= 50000000:
                raise LinkDenied(422, "MOMO_AMOUNT_OUT_OF_RANGE")
            request_id = uuid5(NAMESPACE_URL, f"rental:momo:{invoice.id}:{key}").hex if key else uuid4().hex
            previous = repo.payment_attempt(db, invoice.id, request_id=request_id)
            if previous is not None and previous.status != "PENDING":
                raise LinkDenied(409, "PAYMENT_ATTEMPT_CLOSED")
            existing = previous or repo.payment_attempt(db, invoice.id, status="PENDING")
            if existing is not None:
                return self.view(existing, reused=True)
            attempt = m.PaymentAttempt(
                id=uuid4(), invoice_id=invoice.id, provider="MOMO", amount=invoice.total_amount,
                order_id=uuid4().hex, request_id=request_id, status="PENDING",
            )
            db.add(attempt)

        # The provider can deliver IPN even before create returns.
        self._create(attempt)
        with self.sessions() as db:
            current = db.get(m.PaymentAttempt, attempt.id)
            if current.status not in ("PENDING", "SUCCESS"):
                raise LinkDenied(409, "MOMO_CREATE_REJECTED")
            return self.view(current, reused=False)

    def _create(self, attempt):
        try:
            result = self.momo.create(attempt)
        except MomoUnavailable:
            return
        with self.sessions.begin() as db:
            db.get(m.Invoice, attempt.invoice_id, with_for_update=True)
            current = db.get(m.PaymentAttempt, attempt.id, with_for_update=True)
            if current.status != "PENDING":
                return
            current.result_code = str(result.resultCode)
            if result.resultCode == 0:
                current.pay_url = result.payUrl
            elif result.resultCode in CREATE_REJECTIONS | FINAL_FAILURES and not current.pay_url:
                current.status = "FAILED"

    def receive_ipn(self, ipn):
        if not self.momo.enabled:
            raise LinkDenied(503, "MOMO_UNAVAILABLE")
        valid = self.momo.verify_ipn(ipn)
        fingerprint = hashlib.sha256(json.dumps(ipn.model_dump(), sort_keys=True).encode()).hexdigest()
        with self.sessions.begin() as db:
            attempt_id = invoice_id = None
            if valid:
                match = db.execute(select(m.PaymentAttempt.id, m.PaymentAttempt.invoice_id).where(
                    m.PaymentAttempt.order_id == ipn.orderId, m.PaymentAttempt.provider == "MOMO",
                )).one_or_none()
                if match:
                    attempt_id, invoice_id = match
            if not valid:
                outcome = "INVALID_SIGNATURE"
            elif attempt_id is None:
                outcome = "UNKNOWN_ORDER"
            else:
                invoice = db.get(m.Invoice, invoice_id, with_for_update=True)
                attempt = db.get(m.PaymentAttempt, attempt_id, with_for_update=True)
                if attempt.request_id != ipn.requestId:
                    outcome = "UNKNOWN_ORDER"
                elif ipn.amount != attempt.amount or ipn.amount != invoice.total_amount:
                    outcome = "AMOUNT_MISMATCH"
                else:
                    outcome = self._apply(db, invoice, attempt, ipn, from_query=False)
            db.add(m.PaymentWebhookReceipt(
                payment_attempt_id=attempt_id, order_id=ipn.orderId, payload_fingerprint=fingerprint,
                signature_valid=valid, processing_result=outcome, processed_at=utcnow(),
            ))
        if outcome == "INVALID_SIGNATURE":
            raise LinkDenied(403, outcome)
        if outcome == "UNKNOWN_ORDER":
            raise LinkDenied(404, outcome)
        if outcome == "AMOUNT_MISMATCH":
            raise LinkDenied(409, outcome)

    def _apply(self, db, invoice, attempt, result, *, from_query):
        if attempt.status == "SUCCESS":
            if result.resultCode == 0 and str(result.transId) != attempt.provider_transaction_id:
                return RECONCILIATION
            return "DUPLICATE"
        if result.resultCode == 0:
            if (not result.transId or result.transId < 0 or invoice.status != "ISSUED"
                    or (attempt.status != "PENDING" and not from_query)):
                return RECONCILIATION
            if attempt.status != "PENDING" and repo.payment_attempt(db, invoice.id, status="PENDING"):
                return RECONCILIATION
            transaction = str(result.transId)
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                       {"key": f"momo-transaction:{transaction}"})
            if db.scalar(select(m.PaymentAttempt.id).where(
                m.PaymentAttempt.provider == "MOMO", m.PaymentAttempt.provider_transaction_id == transaction,
                m.PaymentAttempt.status == "SUCCESS", m.PaymentAttempt.id != attempt.id,
            ).limit(1)):
                return RECONCILIATION
            self._mark_paid(db, invoice, attempt, transaction)
            return "PROCESSED"
        if result.resultCode in FINAL_FAILURES and attempt.status == "PENDING":
            attempt.status = "EXPIRED" if result.resultCode == 1005 else "FAILED"
            attempt.result_code = str(result.resultCode)
            return "PROCESSED"
        return "DUPLICATE" if attempt.status != "PENDING" else RECONCILIATION

    @staticmethod
    def _mark_paid(db, invoice, attempt, transaction):
        now, event_id = utcnow(), uuid4()
        attempt.status = "SUCCESS"
        attempt.provider_transaction_id = transaction
        attempt.confirmed_at = now
        attempt.result_code = "0"
        invoice.status, invoice.paid_at = "PAID", now
        db.add(m.OutboxEvent(
            id=event_id, aggregate_type="Invoice", aggregate_id=invoice.id, event_type="PaymentSucceeded",
            event_version=1, correlation_id=attempt.id, dedupe_key=f"payment.succeeded.v1:{invoice.id}",
            payload={
                "event_id": str(event_id), "event_type": "PaymentSucceeded", "event_version": 1,
                "occurred_at": now.isoformat(), "correlation_id": str(attempt.id), "aggregate_id": str(invoice.id),
                "data": {
                    "invoice_id": str(invoice.id), "payment_attempt_id": str(attempt.id),
                    "provider_transaction_id": transaction, "paid_amount": attempt.amount,
                    "recipient_email": invoice.tenant_email_snapshot, "invoice_code": invoice.invoice_code,
                    "tenant_name": invoice.tenant_name_snapshot, "room_code": invoice.room_code_snapshot,
                    "period_start": invoice.period_start.isoformat(),
                    "period_end_exclusive": invoice.period_end.isoformat(), "paid_at": now.isoformat(),
                },
            },
        ))

    def reconcile(self, request):
        if not self.momo.enabled:
            raise LinkDenied(503, "MOMO_UNAVAILABLE")
        cutoff = utcnow() - timedelta(seconds=self.momo.settings.momo_reconcile_seconds)
        with self.sessions() as db:
            candidates = repo.payment_candidates(db, cutoff, request.limit, request.payment_attempt_id)
        counts = dict.fromkeys(("checked_count", "succeeded_count", "failed_count", "still_pending_count"), 0)
        for attempt_id in candidates:
            status = self._reconcile_one(attempt_id)
            counts["checked_count"] += 1
            name = {"SUCCESS": "succeeded_count", "FAILED": "failed_count", "EXPIRED": "failed_count"}
            counts[name.get(status, "still_pending_count")] += 1
        return counts

    def _reconcile_one(self, attempt_id):
        with self.sessions.begin() as db:
            attempt = db.get(m.PaymentAttempt, attempt_id, with_for_update=True)
            attempt.last_reconciled_at = utcnow()
        try:
            result = self.momo.query(attempt)
        except MomoUnavailable:
            return "PENDING"
        if (result.resultCode == 42 and attempt.status == "PENDING" and not attempt.pay_url
                and attempt.created_at <= utcnow() - timedelta(seconds=self.momo.settings.momo_reconcile_seconds)):
            # Retry the same merchant order and request ID after MoMo reports no order.
            self._create(attempt)
        with self.sessions.begin() as db:
            invoice = db.get(m.Invoice, attempt.invoice_id, with_for_update=True)
            current = db.get(m.PaymentAttempt, attempt.id, with_for_update=True)
            if result.amount == current.amount == invoice.total_amount:
                outcome = self._apply(db, invoice, current, result, from_query=True)
                if outcome in ("PROCESSED", "DUPLICATE") and result.resultCode in FINAL_FAILURES | {0}:
                    db.execute(update(m.PaymentWebhookReceipt).where(
                        m.PaymentWebhookReceipt.payment_attempt_id == current.id,
                        m.PaymentWebhookReceipt.processing_result == RECONCILIATION,
                    ).values(processing_result=outcome, processed_at=utcnow()))
                if outcome == RECONCILIATION:
                    return "PENDING"
            if current.status in ("FAILED", "EXPIRED") and result.resultCode == 0:
                return "PENDING"
            return current.status
