"""Auth HTTP entrypoint: domain routers, contract-compatible errors and readiness."""

from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import router as public_router
from app.api_internal import router as internal_router
from app.db import get_engine

app = FastAPI(title="auth", version="1.0.0")
app.include_router(public_router)
app.include_router(internal_router)


def correlation_id(request: Request) -> str:
    try:
        return str(UUID(request.headers.get("x-correlation-id", "")))
    except (ValueError, TypeError):
        return str(uuid4())


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    messages = {
        401: ("UNAUTHORIZED", "Invalid credentials or access token"),
        403: ("FORBIDDEN", "Access denied"),
        404: ("NOT_FOUND", "Resource not found"),
        503: ("DEPENDENCY_UNAVAILABLE", "Service dependency unavailable"),
    }
    code, message = messages.get(exc.status_code, ("HTTP_ERROR", "Request failed"))
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": code, "message": message, "correlation_id": correlation_id(request)},
        headers={**(exc.headers or {}), "Cache-Control": "no-store"},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not echo validation inputs; password could be present in the request.
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": "Request validation failed", "correlation_id": correlation_id(request)},
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
def ready() -> dict[str, str]:
    """Liveness is /health; readiness proves DB connectivity and Alembic marker."""
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
