# AI Access Control Center

AI Access Control Center is a production-style internal portal for governed, temporary access to enterprise generative AI platforms. It demonstrates enterprise authentication boundaries, server-side RBAC, request approval workflows, policy evaluation, provider adapter boundaries, budget governance, user notifications, audit logging, Docker-based local development, and CI readiness.

## Current Phase

Phase 1 foundation is implemented with a working FastAPI API, Next.js portal, development users, mock provider provisioning, baseline tests, Docker Compose, and documentation. Live AWS, Azure, Google Cloud, Microsoft Graph, and GitHub integrations are intentionally adapter boundaries in this phase.

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

Local development authentication uses the `x-dev-user` header. The web app includes an identity switcher for the seeded users.

## Implemented Features

- FastAPI application with health endpoints and OpenAPI docs.
- Development authentication and server-side RBAC.
- Seeded enterprise roles and users.
- Access request API with backend validation.
- Explicit request state machine.
- Versioned standard policy evaluation.
- Approval workflow with approver and CTO paths.
- Mock provider adapter contract and provisioning flow.
- Append-only audit event model from the application perspective.
- Next.js dashboard with request form, approvals, policy evaluation, notifications, CTO executive reporting, audit export, and spend charts.
- Docker Compose for PostgreSQL, Redis, API, worker, and web.
- GitHub Actions workflow for backend, frontend, Docker, and Terraform validation.

## Testing

```bash
make test
make lint
make typecheck
```

Backend tests cover state transitions, RBAC denial/audit logging, request submission, notifications, executive reporting, audit export, policy evaluation, and mock provisioning through approval. Frontend tests cover request form validation.
Playwright covers the seeded interview demo lifecycle end to end.

For a clean local SQLite migration check:

```bash
rm -f apps/api/control_plane.db
cd apps/api && DATABASE_URL=sqlite:///./control_plane.db uv run alembic upgrade head
```

## Known Limitations

- OIDC/PKCE is represented as an architecture boundary; local auth uses deterministic development identities.
- Provider adapters run in mock mode only.
- The API still creates local tables at startup for demo velocity, with Alembic migrations available for clean database setup.
- Worker and scheduler are scaffolded; jobs execute inline for the first approval/provisioning slice.
- `npm audit` currently reports a moderate Next/PostCSS transitive advisory where `next@latest` still bundles the affected range.

## Roadmap

1. Move provisioning, usage, budget, lifecycle actions, and notifications to durable async jobs.
2. Expand live-safe provider configuration and read-only health checks.
3. Add repository-layer and service-layer coverage around provider adapters.
4. Replace local development authentication with OIDC/PKCE and enterprise group mapping.
5. Add cost allocation exports and scheduled delivery.
