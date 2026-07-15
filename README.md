# AI Access Control Center

AI Access Control Center is a production-style internal portal for governed, temporary access to enterprise generative AI platforms. It demonstrates enterprise authentication boundaries, server-side RBAC, request approval workflows, policy evaluation, provider adapter boundaries, budget governance, user notifications, audit logging, Docker-based local development, and CI readiness.

![AI Access Control Center dashboard](docs/images/dashboard.png)

## Current Phase

Phase 1 foundation is implemented with a working FastAPI API, Next.js portal, development users, mock provider provisioning, baseline tests, Docker Compose, and documentation. Live AWS, Azure, Google Cloud, Microsoft Graph, and GitHub integrations expose SDK/config readiness checks and guarded least-privilege operation profiles behind a feature flag.

## Local Setup

```bash
make setup
make test
make e2e
make compose-config
make dev
```

The API runs on `http://localhost:8000` and the web portal runs on `http://localhost:3000` when started through Docker Compose.
Local values in `.env` are loaded by Docker Compose and by the API settings layer when running from `apps/api`.
Use the Compose host name `postgres` only inside Docker Compose. For a host-local PostgreSQL install,
use a URL such as `postgresql+psycopg://control_plane:control_plane@127.0.0.1:5432/control_plane`.

If those host ports are already taken, run:

```bash
API_PORT=8010 WEB_PORT=3001 NEXT_PUBLIC_API_URL=http://localhost:8010 make dev
```

The Makefile also clears Snap VS Code's revision-specific `XDG_DATA_HOME` before Docker-compatible
commands, which avoids a local Podman storage database mismatch seen on this workstation.

## Demo Users

- `employee@example.local`
- `owner@example.local`
- `approver@example.local`
- `security@example.local`
- `admin@example.local`
- `auditor@example.local`
- `cto@example.local`

Local development authentication uses the `x-dev-user` header while `DEV_AUTH_ENABLED=true`, and
the web app includes an identity switcher for the seeded users. With
`NEXT_PUBLIC_AUTH_MODE=oidc` and `DEV_AUTH_ENABLED=false`, the web app starts an
authorization-code-with-PKCE login, lets the API exchange the code, stores refresh tokens
server-side behind an HttpOnly session cookie, and calls the API with short-lived bearer tokens. The
API validates signed OIDC-compatible tokens with matching issuer and audience claims. Optional OIDC
group-to-role mapping can synchronize enterprise group claims to application roles.

## Implemented Features

- FastAPI application with health, observability, and OpenAPI docs.
- Development authentication, OIDC-compatible API bearer-token validation, enterprise group-to-role mapping, and server-side RBAC.
- Seeded enterprise roles and users.
- Access request API with backend validation.
- Explicit request state machine.
- Versioned standard policy evaluation.
- Approval workflow with approver and CTO paths.
- Mock provider adapter contract with durable queued provisioning jobs and local inline execution.
- Live provider adapter boundaries with safe readiness checks and feature-flagged least-privilege mutating operations.
- Signed provider webhook endpoint with replay-window validation.
- Process-local API rate limiting with response headers for local/demo protection.
- Append-only audit event model from the application perspective.
- Next.js dashboard with request form, project membership and scoped audit visibility, member addition, ownership reassignment, project suspension, request cancellation, extension workflow, approvals with additional-information handling, CTO override, approval history, role-change, operational health, lifecycle job retry, and provisioning evidence visibility, policy evaluation, policy version/retention management, provider health/configuration/credential visibility, credential rotation evidence, usage and budget evidence, incident handling, notification delivery state, CTO executive reporting, audit/cost allocation export and queued scheduled delivery, and spend charts.
- Docker Compose for PostgreSQL, Redis, API, worker, and web.
- Production-style Dockerfiles with Node 24 web builds, uv-locked API installs, and a uv-backed worker command.
- GitHub Actions workflow for backend, frontend, migration, high-severity dependency audit, Docker, and Terraform validation.

## Testing

```bash
make test
make lint
make typecheck
make migration-check
make security-audit
```

Backend tests cover state transitions, RBAC denial/audit logging, request submission, trace/correlation propagation, rate limiting, queued lifecycle worker execution, project ownership and scoped audit visibility, project member management/reassignment/suspension, approval information requests, CTO override, approval history, role-change and provisioning evidence visibility, provider retryable failure handling, provider configuration modes, guarded live-provider operations, provider credential inventory/rotation, cancellation, extension requests, incidents, notifications, executive reporting, usage/cost/budget evidence, audit/cost allocation export, policy versioning/retention/evaluation, and mock provisioning through approval. Frontend tests cover request form validation.
Playwright covers the seeded interview demo lifecycle end to end.

For a clean local SQLite migration check:

```bash
rm -f apps/api/control_plane.db
cd apps/api && DATABASE_URL=sqlite:///./control_plane.db uv run alembic upgrade head
```

## Known Limitations

- OIDC-compatible API bearer-token validation, group-to-role mapping, frontend PKCE login initiation, and server-managed refresh-token sessions are implemented.
- Live provider mutating operations are intentionally disabled until `PROVIDER_LIVE_OPERATIONS_ENABLED=true`; when enabled, provider assignments use guarded least-privilege operation profiles and SDK/config readiness checks.
- The API still creates local tables at startup for demo velocity, with Alembic migrations available for clean database setup.
- Provisioning, usage/budget processing, restore, archive/deprovision, cost allocation delivery, and notification delivery are durably tracked and can be drained by the worker; local inline execution remains enabled by default for demo velocity.
- `npm audit --audit-level=high` passes; `npm audit --audit-level=moderate` currently reports the known Next/PostCSS transitive advisory where the suggested forced fix downgrades Next to an unusable legacy release.

## Roadmap

1. Replace guarded live-provider operation profiles with provider-specific API calls after credentials, tenancy, and rollback procedures are approved.
2. Add repository-layer and service-layer coverage around provider adapters.
3. Move scheduled report delivery from local worker evidence to external email infrastructure.
4. Track and resolve the remaining moderate Next/PostCSS advisory when a non-breaking Next release is available.
