"""Service-only invoice link issuance."""
from datetime import datetime
from secrets import compare_digest
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api import error
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Invoice
from app.reminders import reminder_reason
from app.schemas import AccessLink, AccessLinkRequest
from app.service import LinkDenied, VN, create_access_link

router = APIRouter(prefix="/internal/v1", include_in_schema=False)


def require_service_token(
    settings: Settings = Depends(get_settings),
    credential: str | None = Header(None, alias="X-Service-Token"),
):
    if not credential or not compare_digest(credential.encode(), settings.service_token.get_secret_value().encode()):
        raise error(403, "INTERNAL_ONLY", "Valid service credentials required")


@router.post("/invoices/{invoice_id}/access-links", status_code=201, response_model=AccessLink,
             dependencies=[Depends(require_service_token)])
def issue_link(invoice_id: UUID, payload: AccessLinkRequest, db: Session = Depends(get_db),
               settings: Settings = Depends(get_settings)):
    try:
        return create_access_link(db, invoice_id, payload, settings)
    except LinkDenied as exc:
        raise error(exc.status, exc.code, "Access link could not be issued") from exc


@router.get("/invoices/{invoice_id}/reminder-eligibility", dependencies=[Depends(require_service_token)])
def reminder_eligibility(invoice_id: UUID, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise error(404, "INVOICE_NOT_FOUND", "Invoice does not exist")
    reason = reminder_reason(invoice, datetime.now(VN).date())
    return {"invoice_id": invoice_id, "eligible": reason == "OUTSTANDING", "reason": reason}
