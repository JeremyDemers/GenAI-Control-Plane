from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
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
