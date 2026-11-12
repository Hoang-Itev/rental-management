"""Public read-only invoice projection."""
import re

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api import error
from app.db import get_db
from app.schemas import PublicInvoiceView
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
