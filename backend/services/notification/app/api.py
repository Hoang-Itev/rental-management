from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import repository as repo
from app.db import get_db
from app.models import EmailJob
from app.schemas import EmailJobPage, EmailJobView
from app.service import reset_failed_job

router = APIRouter(prefix="/api/v1/email-jobs")


def api_error(status, code, message):
    return HTTPException(status, {"code": code, "message": message, "correlation_id": str(uuid4())})


@router.get("", response_model=EmailJobPage, response_model_exclude_none=True)
def list_jobs(status: str | None = None, email_type: str | None = None,
              page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
              db: Session = Depends(get_db)):
    filters = [column == value for column, value in (
        (EmailJob.status, status), (EmailJob.email_type, email_type),
    ) if value is not None]
    return repo.page(db, filters, page, page_size)


def require_job(db, job_id, *, lock=False):
    job = db.get(EmailJob, job_id, with_for_update=lock)
    if job is None:
        raise api_error(404, "EMAIL_JOB_NOT_FOUND", "Email job does not exist")
    return job


@router.get("/{job_id}", response_model=EmailJobView, response_model_exclude_none=True)
def get_job(job_id: UUID, db: Session = Depends(get_db)):
    return require_job(db, job_id)


@router.post("/{job_id}/retry", response_model=EmailJobView, response_model_exclude_none=True)
def retry_job(job_id: UUID, db: Session = Depends(get_db)):
    with db.begin():
        job = require_job(db, job_id, lock=True)
        if not reset_failed_job(job):
            raise api_error(409, "EMAIL_JOB_NOT_RETRYABLE", "Only failed email jobs can be retried")
    return job
