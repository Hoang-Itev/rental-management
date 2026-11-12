"""MoMo IPN and owner-triggered reconciliation."""
from collections.abc import Iterator

import httpx
from fastapi import APIRouter, Depends, Response

from app.api import error
from app.config import get_settings
from app.db import get_sessionmaker
from app.momo import MomoClient
from app.payment import PaymentService
from app.schemas import MomoIPN, ReconcilePayments
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


@router.post("/api/v1/jobs/payments/reconcile/run")
def reconcile_payments(payload: ReconcilePayments | None = None,
                       service: PaymentService = Depends(get_payment_service)):
    try:
        return service.reconcile(payload or ReconcilePayments())
    except LinkDenied as exc:
        raise error(exc.status, exc.code, "MoMo reconciliation unavailable") from exc
