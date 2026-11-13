"""MoMo IPN and owner-triggered reconciliation."""
from collections.abc import Iterator

import httpx
from fastapi import APIRouter, Depends, Header, Response

from app.api import error
from app.config import get_settings
from app.db import get_sessionmaker
from app.momo import MomoClient
from app.payment import PaymentService
from app.schemas import MomoIPN, ReconcilePayments, ReconcileResult, SePayIPN
from app.sepay import SePayGateway
from app.sepay_payment import SePayPaymentService
from app.service import LinkDenied

router = APIRouter()


def get_payment_service() -> Iterator[PaymentService]:
    settings = get_settings()
    with httpx.Client(timeout=settings.momo_timeout_seconds, trust_env=False) as http:
        yield PaymentService(get_sessionmaker(), MomoClient(http, settings))


@router.post("/webhooks/momo/ipn", status_code=204)
def receive_momo_ipn(payload: MomoIPN, service: PaymentService = Depends(get_payment_service)):
    try:
        service.receive_ipn(payload)
    except LinkDenied as exc:
        raise error(exc.status, exc.code, "MoMo notification rejected") from exc
    return Response(status_code=204)


@router.post("/api/v1/jobs/payments/reconcile/run", response_model=ReconcileResult)
def reconcile_payments(payload: ReconcilePayments | None = None,
                       service: PaymentService = Depends(get_payment_service)):
    try:
        return service.reconcile(payload or ReconcilePayments())
    except LinkDenied as exc:
        raise error(exc.status, exc.code, "MoMo reconciliation unavailable") from exc


def get_sepay_payment_service() -> SePayPaymentService:
    return SePayPaymentService(get_sessionmaker(), SePayGateway(get_settings()))


@router.post("/webhooks/sepay/ipn", status_code=200)
def receive_sepay_ipn(
    payload: SePayIPN,
    x_secret_key: str | None = Header(None, alias="X-Secret-Key"),
    service: SePayPaymentService = Depends(get_sepay_payment_service),
) -> dict[str, bool]:
    try:
        service.receive_ipn(payload, x_secret_key)
    except LinkDenied as exc:
        raise error(exc.status, exc.code, "SePay notification rejected") from exc
    return {"success": True}
