"""Metering HTTP app; event consumption runs in a separate container."""
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api_internal import router as internal_router
from app.api import router as public_router, alerts_router
from app.db import get_engine

app = FastAPI(title="metering", version="0.3.0")
app.include_router(internal_router)
app.include_router(public_router)
app.include_router(alerts_router)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
def ready() -> dict[str, str]:
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
