# AI Access Control Center

AI Access Control Center is a production-style internal portal for governed, temporary access to enterprise generative AI platforms. It demonstrates enterprise authentication boundaries, server-side RBAC, request approval workflows, policy evaluation, provider adapter boundaries, budget governance, audit logging, Docker-based local development, and CI readiness.

## Current Phase

Phase 1 foundation is implemented with a working FastAPI API, Next.js portal, development users, mock provider provisioning, baseline tests, Docker Compose, and documentation. Live AWS, Azure, Google Cloud, Microsoft Graph, and GitHub integrations are intentionally adapter boundaries in this phase.

## Local Setup

```bash
make setup
make test
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
- Next.js dashboard with request form, approvals, policy evaluation, and spend charts.
- Docker Compose for PostgreSQL, Redis, API, worker, and web.
- GitHub Actions workflow for backend, frontend, Docker, and Terraform validation.

## Testing

```bash
make test
make lint
make typecheck
```

Backend tests cover state transitions, RBAC denial/audit logging, request submission, policy evaluation, and mock provisioning through approval. Frontend tests cover request form validation.

## Known Limitations

- OIDC/PKCE is represented as an architecture boundary; local auth uses deterministic development identities.
- Provider adapters run in mock mode only.
- Alembic migration files are not yet generated; the phase-1 API creates local tables at startup for demo velocity.
- Worker and scheduler are scaffolded; jobs execute inline for the first approval/provisioning slice.
- `npm audit` currently reports a moderate Next/PostCSS transitive advisory where `next@latest` still bundles the affected range.

## Roadmap

1. Add Alembic migrations and repository-layer coverage.
2. Move provisioning, usage, budget, and lifecycle actions to durable async jobs.
3. Expand dashboard views for project owners, auditors, administrators, and executives.
4. Add Playwright end-to-end coverage for the interview demo scenario.
5. Implement live-safe provider configuration and read-only health checks.
