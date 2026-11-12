"""Notification HTTP application."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.api import router
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_engine

app = FastAPI(title="notification", version="0.1.0")


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
    return JSONResponse(exc.detail, status_code=exc.status_code, headers=exc.headers)


app.include_router(router)
