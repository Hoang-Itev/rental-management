"""Room HTTP entrypoint. Nginx auth_request protects /api/v1 routes."""
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import router as public_router
from app.api_internal import router as internal_router
from app.db import get_engine
from app.service import RoomError

app = FastAPI(title="room", version="1.0.0")
app.include_router(public_router)
app.include_router(internal_router)


def correlation_id(request: Request) -> str:
    try:
        return str(UUID(request.headers.get("x-correlation-id", "")))
    except (TypeError, ValueError):
        return str(uuid4())


def error_response(request: Request, status: int, code: str, message: str):
    return JSONResponse(status_code=status,
                        content={"code": code, "message": message, "correlation_id": correlation_id(request)},
                        headers={"Cache-Control": "no-store"})


@app.exception_handler(RoomError)
async def room_error(request: Request, exc: RoomError):
    return error_response(request, exc.status, exc.code, exc.message)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    messages = {401: ("UNAUTHORIZED", "Authentication required"),
                403: ("FORBIDDEN", "Access denied"),
                404: ("NOT_FOUND", "Resource not found"),
                503: ("DEPENDENCY_UNAVAILABLE", "Database not ready")}
    code, message = messages.get(exc.status_code, ("HTTP_ERROR", "Request failed"))
    response = error_response(request, exc.status_code, code, message)
    if exc.headers:
        response.headers.update(exc.headers)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return error_response(request, 422, "VALIDATION_ERROR", "Request validation failed")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
def ready() -> dict[str, str]:
    try:
        with get_engine().connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
            if not revision:
                raise HTTPException(status_code=503, detail="database_not_migrated")
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database_not_ready") from exc
    return {"status": "ready"}
