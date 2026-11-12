"""Landlord invoice endpoints behind the authenticated gateway."""
from collections.abc import Iterator
from datetime import date
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
from app.service import InvoiceConflict, InvoiceService

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
        if invoice.invoice_type != "PERIODIC" or invoice.billing_month is None:
            raise error(409, "INVOICE_CONFLICT", "Only periodic invoices can be issued here")
        month, contract_id = invoice.billing_month, invoice.contract_id
    try:
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
