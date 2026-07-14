# Phase 1 Status

## Completed

- Monorepo scaffold with `apps/api`, `apps/web`, infrastructure, docs, CI, and Make targets.
- FastAPI application with development authentication, RBAC, seeded users, health endpoints, policy evaluation, approval workflow, mock provider provisioning, and audit events.
- SQLAlchemy domain model covering the required control-plane tables.
- Next.js portal with role switching, request submission, request list, approval queue, policy evaluation, and dashboard charts.
- Docker Compose for PostgreSQL, Redis, API, worker, and web.
- Baseline backend and frontend automated tests.

## Verified

- `cd apps/api && uv run pytest`
- `cd apps/api && uv run ruff check .`
- `cd apps/api && uv run mypy app`
- `npm --workspace apps/web run test`
- `npm --workspace apps/web run typecheck`
- `npm --workspace apps/web run lint`
- `npm --workspace apps/web run build`
- Manual local smoke test with API on `8010` and web on `3001` because `8000` and `3000` were already occupied on this workstation.
- `docker compose config --quiet` could not be verified locally because the Docker shim is backed by a Podman storage database with a static-dir mismatch outside the repository.

## Remaining Work

- Generate Alembic migration revisions from the current model.
- Move provisioning, usage, budget, and lifecycle processing into durable asynchronous workers.
- Add Playwright coverage for the full interview demo scenario.
- Expand live-safe provider adapters for AWS, Azure, Google Cloud, Microsoft Graph, and GitHub.
- Track the remaining moderate npm audit advisory for Next's transitive PostCSS dependency; the current `next@latest` still bundles the affected range, and `npm audit fix --force` recommends downgrading to an unusable legacy Next release.
