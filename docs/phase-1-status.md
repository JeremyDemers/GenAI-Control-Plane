# Phase 1 Status

## Completed

- Monorepo scaffold with `apps/api`, `apps/web`, infrastructure, docs, CI, and Make targets.
- FastAPI application with development authentication, OIDC-compatible bearer-token validation, enterprise group-to-role mapping, RBAC, seeded users, health endpoints, policy evaluation, approval workflow, mock provider provisioning, and audit events.
- SQLAlchemy domain model covering the required control-plane tables.
- Next.js portal with role switching, request submission, request list, approval queue, policy evaluation, and dashboard charts.
- Docker Compose for PostgreSQL, Redis, API, worker, and web.
- Baseline backend and frontend automated tests.

## Phase 2/3 Slice Completed

- Initial Alembic migration generated and verified with `alembic upgrade head`.
- Observability now propagates trace IDs, aligns correlation IDs across response headers and audit events, and exposes request/queue telemetry through `/health/observability`.
- API middleware applies local rate limiting with rate-limit headers and correlated `429` responses.
- Provisioning now writes durable queued lifecycle jobs with payloads; local API execution drains them inline by default, and the worker process can drain queued jobs independently.
- Restore and archive/deprovision actions now use durable lifecycle jobs with worker drain support while keeping local inline execution enabled by default.
- Usage and budget processing now queue as lifecycle jobs and can be drained by the worker while preserving local inline execution for demos.
- Notifications now track pending/delivered state, delivery attempts, and worker-driven delivery audit evidence.
- The web portal can start an OIDC authorization-code-with-PKCE login; the API performs code exchange, keeps refresh tokens server-side, and refreshes short-lived bearer tokens through an HttpOnly session cookie.
- Provider webhook callbacks require timestamped HMAC signatures and produce audit evidence on accepted deliveries.
- `PROVIDER_MODE=live` now selects safe live adapter boundaries with provider-specific readiness checks while mutating operations remain disabled by default.
- Local developer lifecycle controls now simulate 70%, 90%, and 100% budget thresholds.
- Budget enforcement suspends assignments, creates incidents, and emits audit events.
- Platform administrators and auditors can view incidents; administrators can resolve them with audit evidence.
- Administrator restore, forced expiration, artifact archival, deprovisioning, and request closure are implemented in mock mode.
- Admins, CTOs, and security auditors can view provisioning, archive, and deprovisioning evidence through `/evidence/provisioning`.
- Frontend developer controls expose assignment cost/token totals, restore, expiration, and archive evidence.
- Auditor view shows recent audit events for the demo lifecycle.
- Security auditors can export recent audit events as CSV through `/audit-events/export`.
- CTOs, platform admins, and auditors can export assignment-level cost allocation CSVs through `/reports/cost-allocation/export`.
- CTOs and platform admins can schedule auditable cost allocation delivery jobs, visible to auditors.
- Cost allocation delivery jobs now queue and complete through the lifecycle worker while preserving local inline execution for demos.
- CTO executive report summarizes request volume, active/suspended projects, remaining budget, provider spend, and cost-center spend.
- Domain endpoints now expose visible provider assignments, usage records, cost records, and per-request budget summaries.
- Frontend usage and budget evidence shows visible assignments, latest usage, latest cost, spend, remaining budget, and data freshness.
- Provider health checks and privileged provider configuration validation are exposed in the dashboard.
- Live provider readiness checks now include installed AWS, Azure, Azure OpenAI, Microsoft Graph, Google Cloud, and GitHub SDK modules.
- Provider credential inventory exposes safe vault-style references, admin-only rotation, due dates, and audit evidence without returning secrets.
- Retryable provider provisioning failures now create failed lifecycle jobs, sanitized failure metadata, requester notifications, and provider failure audit evidence.
- Access request submission creates project membership records, and project owners can review project requests, members, scoped audit history, evidence, and add existing users to a project with audit and notification evidence.
- Project ownership reassignment now supports owner request, proposed-owner acceptance, admin/CTO approval, member-role transfer, notifications, and audit evidence.
- Security auditors can view role-change evidence derived from audited project membership and reassignment events.
- CTOs and platform administrators can suspend projects, active requests, and provider assignments with audit and notification evidence.
- Approvers can request additional information, and requesters can respond to requeue the same approval step.
- CTO override approval requires a justification, records approval history, emits audit evidence, and provisions approved requests.
- Approval history is exposed for admin, auditor, and CTO review with request, step, decision, actor, and pending-step context.
- User notification inbox is implemented for request submission, approval handoffs, provisioning, budget thresholds, suspension, restore, and closure.
- Employees can cancel pending requests and request access extensions; CTOs and platform admins can approve or reject extension requests.
- Platform administrators can publish new active standard-policy versions, and subsequent requests retain the policy version used during evaluation.
- Platform administrators can update artifact retention policy versions, and archive expiration uses the active retention value.
- Root `.env` values are respected by local API settings and Docker Compose interpolation while remaining ignored by git.
- Docker build paths use Node 24 for the web image, locked uv dependency sync for the API image, and a uv-backed worker command.
- Docker Compose now healthchecks API and web services and waits for healthy API/Postgres/Redis dependencies before starting the worker and web service.
- Playwright now covers the full seeded interview demo lifecycle in Chromium.
- Admins can list lifecycle jobs in the portal and request retry for queued or failed jobs.
- CI now validates Alembic migrations against a clean SQLite database and gates high-severity npm advisories.

## Verified

- `cd apps/api && uv run pytest`
- `cd apps/api && uv run ruff check .`
- `cd apps/api && uv run mypy app`
- `npm --workspace apps/web run test`
- `npm --workspace apps/web run typecheck`
- `npm --workspace apps/web run lint`
- `npm --workspace apps/web run test:e2e`
- `npm --workspace apps/web run build`
- `make migration-check`
- `make security-audit`
- Manual local smoke test with API on `8010` and web on `3001` because `8000` and `3000` were already occupied on this workstation.
- `make compose-config`
- `podman build -f infrastructure/docker/api.Dockerfile -t genai-control-plane-api:test .`
- `podman build -f infrastructure/docker/web.Dockerfile -t genai-control-plane-web:test .`
- `rm -f apps/api/control_plane.db && cd apps/api && DATABASE_URL=sqlite:///./control_plane.db uv run alembic upgrade head`

## Remaining Work

- Add server-managed OIDC refresh-token handling.
- Implement concrete least-privilege mutating provider operations behind the live adapter feature flag.
- Track the remaining moderate npm audit advisory for Next's transitive PostCSS dependency; the current `next@latest` still bundles the affected range, and `npm audit fix --force` recommends downgrading to an unusable legacy Next release.
