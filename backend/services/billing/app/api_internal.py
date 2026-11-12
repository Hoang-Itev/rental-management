"""Service-only invoice link issuance."""
from secrets import compare_digest
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api import error
from app.config import Settings, get_settings
from app.db import get_db
from app.schemas import AccessLink, AccessLinkRequest
from app.service import LinkDenied, create_access_link

router = APIRouter(prefix="/internal/v1", include_in_schema=False)


@router.post("/invoices/{invoice_id}/access-links", status_code=201, response_model=AccessLink)
def issue_link(invoice_id: UUID, payload: AccessLinkRequest, db: Session = Depends(get_db),
               settings: Settings = Depends(get_settings),
               credential: str | None = Header(None, alias="X-Service-Token")):
    if not credential or not compare_digest(credential.encode(), settings.service_token.get_secret_value().encode()):
        raise error(403, "INTERNAL_ONLY", "Valid service credentials required")
    try:
        return create_access_link(db, invoice_id, payload, settings)
    except LinkDenied as exc:
        raise error(exc.status, exc.code, "Access link could not be issued") from exc
