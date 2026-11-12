"""Landlord invoice endpoints behind the authenticated gateway."""
from collections.abc import Iterator
from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m, repository as repo, schemas as s
from app.clients import BillingClients, DependencyUnavailable
from app.config import get_settings
from app.db import get_db, get_sessionmaker
from app.reminders import enqueue_reminder
from app.service import InvoiceConflict, InvoiceService, LinkDenied

router = APIRouter(prefix="/api/v1")


def get_invoice_service() -> Iterator[InvoiceService]:
    settings = get_settings()
    with httpx.Client(timeout=settings.billing_http_timeout_seconds, trust_env=False) as http:
        yield InvoiceService(get_sessionmaker(), BillingClients(http, settings))


def error(status, code, message):
    return HTTPException(status, detail={
        "code": code, "message": message, "correlation_id": str(uuid4()),
    })


@router.get("/invoices", response_model=s.InvoiceList, response_model_exclude_none=True)
def list_invoices(
    contract_id: UUID | None = None,
    status: Literal["DRAFT", "ISSUED", "PAID", "VOID"] | None = None,
    billing_month: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    filters = [(column == value) for column, value in (
        (m.Invoice.contract_id, contract_id), (m.Invoice.status, status),
        (m.Invoice.billing_month, billing_month),
    ) if value is not None]
    return repo.page(db, m.Invoice, filters, page, page_size)


def require_invoice(db, invoice_id):
    invoice = db.get(m.Invoice, invoice_id)
    if invoice is None:
        raise error(404, "INVOICE_NOT_FOUND", "Invoice does not exist")
    return invoice


@router.get("/invoices/{invoice_id}", response_model=s.InvoiceDetail, response_model_exclude_none=True)
def get_invoice(invoice_id: UUID, db: Session = Depends(get_db)):
    return require_invoice(db, invoice_id)


@router.post("/invoices/{invoice_id}/issue", response_model=s.InvoiceDetail, response_model_exclude_none=True)
def issue_invoice(invoice_id: UUID, service: InvoiceService = Depends(get_invoice_service)):
    with service.sessions() as db:
        invoice = require_invoice(db, invoice_id)
        kind, month, contract_id = invoice.invoice_type, invoice.billing_month, invoice.contract_id
    try:
        if kind == "FINAL":
            outcome, _ = service.final(contract_id, expected_id=invoice_id)
        else:
            outcome, _ = service.process(contract_id, month, expected_id=invoice_id)
    except (InvoiceConflict, IntegrityError) as exc:
        raise error(409, "INVOICE_CONFLICT", "Invoice conflicts with the current billing period") from exc
    except DependencyUnavailable as exc:
        raise error(503, "DEPENDENCY_UNAVAILABLE", str(exc)) from exc
    with service.sessions() as db:
        invoice = require_invoice(db, invoice_id)
        if outcome == "waiting" and invoice.status == "DRAFT":
            if invoice.blocked_reason == "DEPENDENCY_UNAVAILABLE":
                raise error(503, "DEPENDENCY_UNAVAILABLE", "Metering unavailable")
            raise error(422, invoice.blocked_reason, "Invoice is waiting for billing data")
        return s.InvoiceDetail.model_validate(invoice)


@router.get("/billing-runs", response_model=s.BillingRunList, response_model_exclude_none=True)
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return repo.page(db, m.BillingRun, [], page, page_size)


@router.post("/billing-runs", status_code=202, response_model=s.BillingRunView, response_model_exclude_none=True)
def enqueue_run(
    payload: s.BillingRunRequest,
    key: str | None = Header(None, alias="Idempotency-Key", min_length=1, max_length=200),
    service: InvoiceService = Depends(get_invoice_service),
):
    try:
        return service.enqueue_month(payload.billing_month, "MANUAL", key)
    except InvoiceConflict as exc:
        raise error(409, "BILLING_RUN_CONFLICT", str(exc)) from exc


@router.get("/invoices/{invoice_id}/payment-attempts", response_model=s.PaymentAttemptList,
            response_model_exclude_none=True)
def list_payment_attempts(
    invoice_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    require_invoice(db, invoice_id)
    return repo.page(db, m.PaymentAttempt, [m.PaymentAttempt.invoice_id == invoice_id], page, page_size)


@router.post("/invoices/{invoice_id}/reminders", response_model=s.InvoiceDetail,
             response_model_exclude_none=True)
def request_reminder(invoice_id: UUID, db: Session = Depends(get_db)):
    try:
        with db.begin():
            invoice = db.get(m.Invoice, invoice_id, with_for_update=True)
            if invoice is None:
                raise error(404, "INVOICE_NOT_FOUND", "Invoice does not exist")
            enqueue_reminder(db, invoice, datetime.now(timezone.utc))
            return s.InvoiceDetail.model_validate(invoice)
    except LinkDenied as exc:
        raise error(exc.status, exc.code, "Invoice is not eligible for a reminder") from exc


def invoice_result(service, invoice_id):
    with service.sessions() as db:
        return s.InvoiceDetail.model_validate(require_invoice(db, invoice_id))


@router.post("/final-invoices", status_code=201, response_model=s.InvoiceDetail, response_model_exclude_none=True)
def create_final_invoice(payload: s.FinalInvoiceRequest, service: InvoiceService = Depends(get_invoice_service)):
    try:
        _, invoice_id = service.final(payload.contract_id)
    except (InvoiceConflict, IntegrityError) as exc:
        message = str(exc) if isinstance(exc, InvoiceConflict) else "Invoice period conflicts"
        raise error(409, "FINAL_INVOICE_CONFLICT", message) from exc
    except DependencyUnavailable as exc:
        raise error(503, "DEPENDENCY_UNAVAILABLE", str(exc)) from exc
    return invoice_result(service, invoice_id)


@router.post("/invoices/{invoice_id}/void", response_model=s.InvoiceDetail, response_model_exclude_none=True)
def void_invoice(invoice_id: UUID, payload: s.InvoiceReason,
                 service: InvoiceService = Depends(get_invoice_service)):
    try:
        service.void(invoice_id, payload.reason)
    except LinkDenied as exc:
        raise error(exc.status, exc.code, "Invoice could not be voided") from exc
    return invoice_result(service, invoice_id)


@router.post("/invoices/{invoice_id}/reissue", response_model=s.InvoiceDetail, response_model_exclude_none=True)
def reissue_invoice(invoice_id: UUID, payload: s.InvoiceReason,
                    service: InvoiceService = Depends(get_invoice_service)):
    try:
        replacement_id = service.reissue(invoice_id, payload.reason)
    except LinkDenied as exc:
        raise error(exc.status, exc.code, "Invoice could not be replaced") from exc
    except IntegrityError as exc:
        raise error(409, "INVOICE_CONFLICT", "Replacement conflicts with existing invoices") from exc
    except DependencyUnavailable as exc:
        raise error(503, "DEPENDENCY_UNAVAILABLE", str(exc)) from exc
    return invoice_result(service, replacement_id)


@router.get("/invoices/{invoice_id}/adjustments", response_model=s.AdjustmentList, response_model_exclude_none=True)
def list_adjustments(
    invoice_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    require_invoice(db, invoice_id)
    return repo.page(db, m.InvoiceAdjustment, [m.InvoiceAdjustment.invoice_id == invoice_id], page, page_size)


@router.post("/invoices/{invoice_id}/adjustments", status_code=201,
             response_model=s.AdjustmentView, response_model_exclude_none=True)
def create_adjustment(invoice_id: UUID, payload: s.AdjustmentCreate, db: Session = Depends(get_db),
                      actor: UUID | None = Header(None, alias="X-Auth-User-Id")):
    with db.begin():
        invoice = db.get(m.Invoice, invoice_id, with_for_update=True)
        if invoice is None:
            raise error(404, "INVOICE_NOT_FOUND", "Invoice does not exist")
        if invoice.status != "PAID":
            raise error(409, "INVOICE_NOT_PAID", "Adjustments require a paid invoice")
        adjustment = m.InvoiceAdjustment(invoice_id=invoice_id, created_by=actor, **payload.model_dump())
        db.add(adjustment)
        db.flush()
        return s.AdjustmentView.model_validate(adjustment)


@router.post("/invoice-adjustments/{adjustment_id}/resolve", response_model=s.AdjustmentView,
             response_model_exclude_none=True)
def resolve_adjustment(adjustment_id: UUID, payload: s.ResolveAdjustment, db: Session = Depends(get_db)):
    with db.begin():
        adjustment = db.get(m.InvoiceAdjustment, adjustment_id, with_for_update=True)
        if adjustment is None:
            raise error(404, "ADJUSTMENT_NOT_FOUND", "Adjustment does not exist")
        if adjustment.status == "OPEN":
            adjustment.status = payload.status
            adjustment.resolution_note = payload.resolution_note
            adjustment.resolved_at = datetime.now(timezone.utc)
        elif (adjustment.status, adjustment.resolution_note) != (payload.status, payload.resolution_note):
            raise error(409, "ADJUSTMENT_ALREADY_CLOSED", "Adjustment is already closed")
        return s.AdjustmentView.model_validate(adjustment)
