"""room HTTP application skeleton. Not yet implementing business routes."""
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_engine

app = FastAPI(title="room", version="0.1.0")


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

# TODO: Register API routers once each business feature is implemented.
