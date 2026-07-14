from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import LifecycleJob
from app.observability.middleware import request_metrics
from app.providers.registry import all_provider_adapters

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("select 1"))
    return {"status": "ready"}


@router.get("/providers")
async def providers() -> dict[str, list[dict[str, object]]]:
    checks = [await adapter.health_check() for adapter in all_provider_adapters()]
    return {"providers": checks}


@router.get("/observability")
def observability(db: Session = Depends(get_db)) -> dict[str, object]:
    job_rows = db.execute(
        select(LifecycleJob.status, func.count())
        .select_from(LifecycleJob)
        .group_by(LifecycleJob.status)
    ).all()
    job_status_counts = {str(status): int(count) for status, count in job_rows}
    return {
        "status": "observable",
        "requests": request_metrics.snapshot(),
        "lifecycle_jobs": {
            "status_counts": job_status_counts,
            "queued_or_failed": int(job_status_counts.get("queued", 0))
            + int(job_status_counts.get("failed", 0)),
        },
    }
