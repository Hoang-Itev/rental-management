"""Public read-only invoice projection."""
import re

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api import error
from app.api_webhook import get_payment_service
from app.db import get_db
from app.payment import PaymentService
from app.schemas import MomoPaymentSession, PublicInvoiceView
from app.service import LinkDenied, read_access_link

router = APIRouter(prefix="/public/v1")
PRIVACY_HEADERS = {"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"}


@router.get("/invoices/{token}", response_model=PublicInvoiceView)
def view_invoice(token: str, response: Response, db: Session = Depends(get_db)):
    try:
        if re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
            raise LinkDenied(404, "LINK_NOT_FOUND")
        invoice = read_access_link(db, token)
    except LinkDenied as exc:
        failure = error(exc.status, exc.code, "Invoice link is unavailable")
        failure.headers = PRIVACY_HEADERS
        raise failure from exc
    response.headers.update(PRIVACY_HEADERS)
    return invoice


@router.post("/invoices/{token}/payments/momo", response_model=MomoPaymentSession,
             response_model_exclude_none=True)
def checkout_momo(
    token: str, response: Response, service: PaymentService = Depends(get_payment_service),
    key: str | None = Header(None, alias="Idempotency-Key", min_length=1, max_length=200),
):
    try:
        if re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
            raise LinkDenied(404, "LINK_NOT_FOUND")
        session = service.checkout(token, key)
    except LinkDenied as exc:
        failure = error(exc.status, exc.code, "Unable to start MoMo checkout")
        failure.headers = PRIVACY_HEADERS
        raise failure from exc
    response.headers.update(PRIVACY_HEADERS)
    return session


@router.get("/payments/momo/return", response_class=PlainTextResponse)
def return_from_momo():
    return PlainTextResponse(
        "Hãy mở lại liên kết hóa đơn trong email để kiểm tra trạng thái thanh toán.",
        headers=PRIVACY_HEADERS,
    )
