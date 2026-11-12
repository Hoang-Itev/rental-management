"""Invoice calculation, persistence and issuance."""
from __future__ import annotations
import hashlib
from secrets import token_urlsafe
from datetime import date, datetime, timedelta, timezone
from typing import Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import models as m, repository as repo
from app.calculator import CalculationError, calculate_invoice, first_day_next_month, uncovered_periods
from app.clients import DependencyUnavailable, MissingCutoff
from app.schemas import InvoiceCalculationInput, InvoiceCalculationResult

VN = ZoneInfo("Asia/Ho_Chi_Minh")
BILLABLE_STATUSES = {"ACTIVE", "EXPIRED_PENDING", "ENDED"}


class BillingCalculatorService:
    def calculate(self, payload: InvoiceCalculationInput | Mapping[str, object]) -> InvoiceCalculationResult:
        return calculate_invoice(payload)


class InvoiceConflict(Exception):
    pass


class InvoiceService:
    def __init__(self, sessions, clients):
        self.sessions = sessions
        self.clients = clients

    def _calculate(self, context, start, end):
        boundaries = sorted({
            start, end,
            *(term.effective_from for term in context.terms if start < term.effective_from < end),
            *(term.effective_to for term in context.terms
              if term.effective_to is not None and start < term.effective_to < end),
        })
        usage = [
            line for left, right in zip(boundaries, boundaries[1:])
            for line in self.clients.usage(context, left, right)
        ]
        return calculate_invoice({
            "period_start": start, "period_end": end,
            "terms": context.terms, "usage_segments": usage,
        })

    def _uncovered(self, db, context, start, end, invoice=None):
        covered = repo.covered_periods(
            db, context.contract_id, start, end, invoice.id if invoice else None,
        )
        gaps = uncovered_periods(start, end, covered)
        if len(gaps) > 1:
            raise InvoiceConflict("Uncovered periods are disjoint. Bill earlier gaps separately first.")
        return gaps[0] if gaps else None

    @staticmethod
    def _draft(context, start, end, *, month=None):
        return m.Invoice(
            id=uuid4(), invoice_code=f"INV-{start:%Y%m}-{context.contract_id.hex}-{uuid4().hex[:8]}",
            contract_id=context.contract_id, invoice_type="PERIODIC" if month is not None else "FINAL",
            billing_month=month, status="DRAFT", total_amount=0, revision=1,
            period_start=start, period_end=end, due_date=datetime.now(VN).date().replace(day=5),
        )

    @staticmethod
    def _snapshot(invoice, context, start, end):
        invoice.room_id = context.room_id
        invoice.period_start, invoice.period_end = start, end
        invoice.tenant_name_snapshot = context.tenant_name
        invoice.tenant_email_snapshot = context.tenant_email
        invoice.room_code_snapshot = context.room_code

    def _calculate_for_issue(self, invoice, context):
        if not context.tenant_email:
            return None, "MISSING_RECIPIENT_EMAIL"
        try:
            return self._calculate(context, invoice.period_start, invoice.period_end), None
        except MissingCutoff:
            return None, "PENDING_CUTOFF"
        except DependencyUnavailable:
            return None, "DEPENDENCY_UNAVAILABLE"
        except CalculationError as exc:
            return None, exc.code
        except ValidationError:
            return None, "INVALID_BILLING_DATA"

    @staticmethod
    def _issue(db, invoice, result, correlation_id=None):
        now = datetime.now(timezone.utc)
        for old_item in invoice.items:
            db.delete(old_item)
        invoice.items = [m.InvoiceItem(**line.model_dump()) for line in result.items]
        invoice.status = "ISSUED"
        invoice.blocked_reason = None
        invoice.total_amount = result.total_amount
        invoice.issued_at = now
        invoice.due_date = now.astimezone(VN).date().replace(day=5)
        event_id = uuid4()
        trace = correlation_id or event_id
        db.add(m.OutboxEvent(
            id=event_id, aggregate_type="Invoice", aggregate_id=invoice.id,
            event_type="InvoiceIssued", event_version=1,
            correlation_id=trace, dedupe_key=f"invoice.issued.v1:{invoice.id}",
            payload={
                "event_id": str(event_id), "event_type": "InvoiceIssued", "event_version": 1,
                "occurred_at": now.isoformat(), "correlation_id": str(trace),
                "aggregate_id": str(invoice.id),
                "data": {
                    "invoice_id": str(invoice.id), "contract_id": str(invoice.contract_id),
                    "invoice_code": invoice.invoice_code, "recipient_email": invoice.tenant_email_snapshot,
                    "tenant_name": invoice.tenant_name_snapshot, "room_code": invoice.room_code_snapshot,
                    "total_amount": invoice.total_amount, "due_date": invoice.due_date.isoformat(),
                    "period_start": invoice.period_start.isoformat(), "period_end_exclusive": invoice.period_end.isoformat(),
                },
            },
        ))

    def _prepare(self, db, invoice, context, start, end, correlation_id=None):
        self._snapshot(invoice, context, start, end)
        result, blocked = self._calculate_for_issue(invoice, context)
        if blocked:
            invoice.blocked_reason = blocked
            return "waiting", invoice.id
        self._issue(db, invoice, result, correlation_id)
        return "issued", invoice.id

    def process(self, contract_id: UUID, month: date, *, expected_id: UUID | None = None,
                correlation_id: UUID | None = None) -> tuple[str, UUID | None]:
        if month.day != 1:
            raise InvoiceConflict("Billing month must start on day 1")
        following_month = first_day_next_month(month)
        with self.sessions.begin() as db:
            repo.lock_contract(db, contract_id)
            invoice = repo.periodic_invoice(db, contract_id, month)
            if expected_id is not None and (invoice is None or invoice.id != expected_id):
                raise InvoiceConflict("Invoice is no longer the current periodic invoice")
            if invoice is not None and invoice.status != "DRAFT":
                return "skipped", invoice.id
            if invoice is None and repo.periodic_was_voided(db, contract_id, month):
                return "skipped", None

            context = self.clients.context(contract_id)
            start = max(month, context.chargeable_from)
            end = min(following_month, context.chargeable_to_exclusive)
            if context.contract_status not in BILLABLE_STATUSES or start >= end:
                if invoice is not None:
                    invoice.blocked_reason = "CONTRACT_NOT_BILLABLE"
                    return "waiting", invoice.id
                return "skipped", None

            gap = self._uncovered(db, context, start, end, invoice)
            if gap is None:
                if invoice is not None:
                    invoice.blocked_reason = "PERIOD_ALREADY_COVERED"
                    return "waiting", invoice.id
                return "skipped", None
            if invoice is None:
                invoice = self._draft(context, *gap, month=month)
                db.add(invoice)
            return self._prepare(db, invoice, context, *gap, correlation_id)

    def final(self, contract_id, *, expected_id=None):
        with self.sessions.begin() as db:
            repo.lock_contract(db, contract_id)
            invoice = repo.final_invoice(db, contract_id)
            if expected_id is not None and (invoice is None or invoice.id != expected_id):
                raise InvoiceConflict("Invoice is no longer the current final invoice")
            if invoice is not None and invoice.status != "DRAFT":
                return "skipped", invoice.id
            context = self.clients.context(contract_id)
            if context.contract_status != "ENDED" or context.chargeable_from >= context.chargeable_to_exclusive:
                raise InvoiceConflict("A final invoice requires an ended contract")
            gap = self._uncovered(db, context, context.chargeable_from, context.chargeable_to_exclusive, invoice)
            if gap is None:
                raise InvoiceConflict("The whole contract period is already covered")
            if invoice is None:
                invoice = self._draft(context, *gap)
                db.add(invoice)
            return self._prepare(db, invoice, context, *gap)

    @staticmethod
    def _locked_invoice(db, invoice_id):
        contract_id = db.scalar(select(m.Invoice.contract_id).where(m.Invoice.id == invoice_id))
        if contract_id is None:
            raise LinkDenied(404, "INVOICE_NOT_FOUND")
        repo.lock_contract(db, contract_id)
        return db.get(m.Invoice, invoice_id, with_for_update=True)

    @staticmethod
    def _check_voidable(db, invoice):
        if invoice.status == "PAID" or repo.payment_attempt(db, invoice.id, status="PENDING"):
            raise LinkDenied(409, "INVOICE_HAS_PAYMENT")

    @staticmethod
    def _void(db, invoice, reason):
        now = datetime.now(timezone.utc)
        invoice.status = "VOID"
        invoice.void_reason = reason
        invoice.voided_at = now
        repo.revoke_invoice_tokens(db, invoice.id, now)

    def void(self, invoice_id, reason):
        with self.sessions.begin() as db:
            invoice = self._locked_invoice(db, invoice_id)
            if invoice.status != "VOID":
                self._check_voidable(db, invoice)
                self._void(db, invoice, reason)
        return invoice_id

    def reissue(self, invoice_id, reason):
        with self.sessions.begin() as db:
            original = self._locked_invoice(db, invoice_id)
            existing = db.scalar(select(m.Invoice.id).where(m.Invoice.replaces_invoice_id == original.id))
            if existing is not None:
                return existing
            if original.status != "ISSUED":
                raise LinkDenied(409, "INVOICE_NOT_REISSUABLE")
            self._check_voidable(db, original)
            context = self.clients.context(original.contract_id)
            if (context.contract_status not in BILLABLE_STATUSES
                    or (original.invoice_type == "FINAL" and context.contract_status != "ENDED")
                    or original.period_start < context.chargeable_from
                    or original.period_end > context.chargeable_to_exclusive):
                raise LinkDenied(409, "INVOICE_PERIOD_CHANGED")
            replacement = self._draft(context, original.period_start, original.period_end,
                                      month=original.billing_month if original.invoice_type == "PERIODIC" else None)
            self._snapshot(replacement, context, original.period_start, original.period_end)
            replacement.revision = original.revision + 1
            replacement.replaces_invoice_id = original.id
            result, blocked = self._calculate_for_issue(replacement, context)
            if blocked:
                raise LinkDenied(503 if blocked == "DEPENDENCY_UNAVAILABLE" else 422, blocked)

            self._void(db, original, reason)
            db.flush()  # Release the old live period before inserting the replacement.
            db.add(replacement)
            self._issue(db, replacement, result)
        return replacement.id

    def enqueue_month(self, month: date, trigger: str, key: str | None = None):
        if month.day != 1 or month >= datetime.now(VN).date().replace(day=1):
            raise InvoiceConflict("Select the first day of a closed billing month")
        run_id = uuid5(NAMESPACE_URL, f"rental-management:billing:{trigger}:{key}") if key else uuid4()
        with self.sessions.begin() as db:
            repo.lock_contract(db, run_id)
            run = db.get(m.BillingRun, run_id)
            if run is None:
                run = m.BillingRun(id=run_id, billing_month=month, trigger_type=trigger, status="RUNNING")
                db.add(run)
            elif run.billing_month != month:
                raise InvoiceConflict("Idempotency-Key already used for another billing month")
            elif trigger == "SCHEDULED" and run.status == "FAILED":
                run.status = "RUNNING"
                run.finished_at = None
                for outcome in ("issued", "waiting", "skipped", "failed"):
                    setattr(run, outcome + "_count", 0)
            db.flush()
        return run

    def execute_run(self, run_id: UUID):
        with self.sessions() as db:
            run = db.get(m.BillingRun, run_id)
            month = run.billing_month
        counts = dict.fromkeys(("issued", "waiting", "skipped", "failed"), 0)
        completed = False
        try:
            for contract_id in self.clients.billable(month, first_day_next_month(month)):
                try:
                    outcome, _ = self.process(contract_id, month, correlation_id=run_id)
                    counts[outcome] += 1
                except (DependencyUnavailable, IntegrityError, InvoiceConflict):
                    counts["failed"] += 1
            completed = counts["failed"] == 0
        except DependencyUnavailable:
            counts["failed"] += 1
        finally:
            with self.sessions.begin() as db:
                run = db.get(m.BillingRun, run_id)
                for outcome, count in counts.items():
                    setattr(run, outcome + "_count", count)
                run.status = "COMPLETED" if completed else "FAILED"
                run.finished_at = datetime.now(timezone.utc)
        return run


class LinkDenied(Exception):
    def __init__(self, status, code):
        self.status = status
        self.code = code


def hash_link_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_access_link(db, invoice_id, request, settings):
    from app.reminders import reminder_reason
    from app.schemas import AccessLink

    with db.begin():
        invoice = db.get(m.Invoice, invoice_id, with_for_update=True)
        if invoice is None:
            raise LinkDenied(404, "INVOICE_NOT_FOUND")
        if invoice.status != "ISSUED":
            raise LinkDenied(409, "INVOICE_NOT_ISSUED")
        source = db.get(m.OutboxEvent, request.source_event_id)
        if (source is None or source.event_type not in ("InvoiceIssued", "InvoiceReminderRequested") or source.aggregate_id != invoice.id
                or source.payload.get("data", {}).get("recipient_email") != request.recipient_email
                or invoice.tenant_email_snapshot != request.recipient_email):
            raise LinkDenied(403, "LINK_RECIPIENT_MISMATCH")
        if source.event_type == "InvoiceReminderRequested" and reminder_reason(invoice, datetime.now(VN).date()) != "OUTSTANDING":
            raise LinkDenied(409, "INVOICE_NOT_REMINDABLE")
        token = token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(seconds=settings.invoice_link_ttl_seconds)
        db.add(m.InvoiceAccessToken(invoice_id=invoice.id, token_hash=hash_link_token(token), expires_at=expires))
    return AccessLink(url=f"{str(settings.public_base_url).rstrip('/')}/public/v1/invoices/{token}", expires_at=expires)


def read_access_link(db, token):
    from app.schemas import PublicInvoiceView

    now = datetime.now(timezone.utc)
    with db.begin():
        link = repo.usable_invoice_link(db, hash_link_token(token), now)
        if link is None:
            raise LinkDenied(404, "LINK_NOT_FOUND")
        invoice = link.invoice
        link.last_used_at = now
        return PublicInvoiceView(
            invoice_code=invoice.invoice_code, room_code=invoice.room_code_snapshot,
            tenant_name=invoice.tenant_name_snapshot, period_start=invoice.period_start,
            period_end=invoice.period_end, status=invoice.status, total_amount=invoice.total_amount,
            due_date=invoice.due_date, items=invoice.items,
        )
