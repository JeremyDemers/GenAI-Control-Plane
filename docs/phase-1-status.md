# Phase 1 Status

## Completed

- Monorepo scaffold with `apps/api`, `apps/web`, infrastructure, docs, CI, and Make targets.
- FastAPI application with development authentication, RBAC, seeded users, health endpoints, policy evaluation, approval workflow, mock provider provisioning, and audit events.
- SQLAlchemy domain model covering the required control-plane tables.
- Next.js portal with role switching, request submission, request list, approval queue, policy evaluation, and dashboard charts.
- Docker Compose for PostgreSQL, Redis, API, worker, and web.
- Baseline backend and frontend automated tests.

## Phase 2/3 Slice Completed

- Initial Alembic migration generated and verified with `alembic upgrade head`.
- Local developer lifecycle controls now simulate 70%, 90%, and 100% budget thresholds.
- Budget enforcement suspends assignments, creates incidents, and emits audit events.
- Administrator restore, forced expiration, artifact archival, deprovisioning, and request closure are implemented in mock mode.
- Frontend developer controls expose assignment cost/token totals, restore, expiration, and archive evidence.
- Auditor view shows recent audit events for the demo lifecycle.
- Security auditors can export recent audit events as CSV through `/audit-events/export`.
- User notification inbox is implemented for request submission, approval handoffs, provisioning, budget thresholds, suspension, restore, and closure.
- Root `.env` values are respected by local API settings and Docker Compose interpolation while remaining ignored by git.
- Playwright now covers the full seeded interview demo lifecycle in Chromium.
- Admins can list lifecycle jobs and request retry for queued or failed jobs.

## Verified

- `cd apps/api && uv run pytest`
- `cd apps/api && uv run ruff check .`
- `cd apps/api && uv run mypy app`
- `npm --workspace apps/web run test`
- `npm --workspace apps/web run typecheck`
- `npm --workspace apps/web run lint`
- `npm --workspace apps/web run test:e2e`
- `npm --workspace apps/web run build`
- Manual local smoke test with API on `8010` and web on `3001` because `8000` and `3000` were already occupied on this workstation.
- `make compose-config`
- `rm -f apps/api/control_plane.db && cd apps/api && DATABASE_URL=sqlite:///./control_plane.db uv run alembic upgrade head`

## Remaining Work

- Move provisioning, usage, budget, lifecycle processing, and notifications from inline execution to durable asynchronous workers.
- Expand live-safe provider adapters for AWS, Azure, Google Cloud, Microsoft Graph, and GitHub.
- Track the remaining moderate npm audit advisory for Next's transitive PostCSS dependency; the current `next@latest` still bundles the affected range, and `npm audit fix --force` recommends downgrading to an unusable legacy Next release.
