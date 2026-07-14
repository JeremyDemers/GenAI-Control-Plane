from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    access_requests,
    approvals,
    audit,
    auth,
    developer,
    health,
    lifecycle_jobs,
    providers,
)
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.models import entities  # noqa: F401
from app.observability.middleware import configure_logging, correlation_middleware
from app.services.seed import seed_development_data


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_development_data(db)
    finally:
        db.close()
    yield


settings = get_settings()
configure_logging()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.middleware("http")(correlation_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(access_requests.router)
app.include_router(approvals.router)
app.include_router(providers.router)
app.include_router(audit.router)
app.include_router(developer.router)
app.include_router(lifecycle_jobs.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "running"}
