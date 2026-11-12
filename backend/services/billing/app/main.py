"""Billing HTTP application."""
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import router
from app.db import get_engine

app = FastAPI(title="billing", version="0.1.0")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Liveness: process is responding; not a database check."""
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
def ready() -> dict[str, str]:
    """Readiness: database connection and recorded Alembic revision exist."""
    try:
        with get_engine().connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar_one_or_none()
            if not revision:
                raise HTTPException(status_code=503, detail="database_not_migrated")
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database_not_ready") from exc
    return {"status": "ready"}


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    detail = exc.detail if isinstance(exc.detail, dict) else {
        "code": str(exc.detail), "message": str(exc.detail), "correlation_id": str(uuid4()),
    }
    return JSONResponse(detail, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse({
        "code": "INVALID_REQUEST", "message": "Invalid request parameters",
        "correlation_id": str(uuid4()),
    }, status_code=422)


app.include_router(router)
