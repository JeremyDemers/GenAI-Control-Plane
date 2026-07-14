import asyncio
import logging

from app.core.database import SessionLocal
from app.services.notifications import deliver_pending_notifications
from app.workers.jobs import run_queued_lifecycle_jobs

logger = logging.getLogger(__name__)


async def drain_once(limit: int = 10, *, include_notifications: bool = False) -> int:
    with SessionLocal() as db:
        processed = await run_queued_lifecycle_jobs(db, limit=limit)
        if include_notifications:
            processed += deliver_pending_notifications(db, limit=limit)
        db.commit()
        return processed


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("local lifecycle worker started")
    while True:
        processed = await drain_once(include_notifications=True)
        if processed:
            logger.info("processed %s worker item(s)", processed)
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
