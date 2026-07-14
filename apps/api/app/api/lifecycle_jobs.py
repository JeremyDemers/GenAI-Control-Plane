from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_correlation_id, require_permission
from app.core.database import get_db
from app.models.entities import LifecycleJob, User
from app.schemas import LifecycleJobOut
from app.services.audit import record_audit_event

router = APIRouter(prefix="/lifecycle-jobs", tags=["lifecycle jobs"])


def job_out(job: LifecycleJob) -> LifecycleJobOut:
    return LifecycleJobOut(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        attempt_count=job.attempt_count,
        idempotency_key=job.idempotency_key,
        payload=job.payload,
        failure_information=job.failure_information,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("", response_model=list[LifecycleJobOut])
def list_jobs(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin:*")),
) -> list[LifecycleJobOut]:
    jobs = db.scalars(
        select(LifecycleJob).order_by(LifecycleJob.created_at.desc()).limit(100)
    ).all()
    return [job_out(job) for job in jobs]


@router.post("/{job_id}/retry", response_model=LifecycleJobOut)
def retry_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("jobs:retry")),
    correlation_id: str = Depends(get_correlation_id),
) -> LifecycleJobOut:
    job = db.get(LifecycleJob, job_id)
    if not job:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Job not found"}
        )
    if job.status not in {"failed", "queued"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "JOB_NOT_RETRYABLE",
                "message": "Only failed or queued jobs can be retried manually.",
            },
        )

    job.status = "queued"
    job.attempt_count += 1
    job.failure_information = {}
    record_audit_event(
        db,
        event_type="lifecycle_job.retry_requested",
        actor_user_id=user.id,
        target_type="lifecycle_job",
        target_id=job.id,
        action="retry",
        result="queued",
        correlation_id=correlation_id,
        metadata_json={"job_type": job.job_type, "attempt_count": job.attempt_count},
    )
    db.commit()
    db.refresh(job)
    return job_out(job)
