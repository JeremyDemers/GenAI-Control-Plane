# Architecture

## System Context

AI Access Control Center separates the application control plane from provider-specific AI platform operations. Employees and reviewers use the Next.js portal. The portal calls the FastAPI API with an OIDC-compatible bearer token in production, or a development identity header locally.

## Containers

- `apps/web`: Next.js React portal.
- `apps/api`: FastAPI API, policy engine, RBAC enforcement, audit logging, and provider orchestration.
- `postgres`: relational control-plane store.
- `redis`: broker/cache boundary for durable jobs; current local provisioning jobs are durably queued in the database and drained by the worker or by local inline execution.
- `worker`: provisioning and lifecycle worker boundary.
- `scheduler`: lifecycle scheduler boundary.

## Component Flow

1. Employee submits an access request.
2. API validates the payload and evaluates the active policy version.
3. API writes the request, policy evaluation, approval steps, and audit event in one transaction.
4. Approvers act on assigned steps according to server-side RBAC.
5. Once final approval is complete, provisioning jobs are queued and drained by the worker or by local inline execution.
6. Provider assignments, resources, costs, usage, incidents, archives, and audit events remain in the control-plane database.

## Provider Adapter Pattern

Cloud-specific behavior is hidden behind `AIProviderAdapter`. Mock adapters are fully functional for demos. Live adapters will use safe feature flags and externally managed credentials.

## Authentication Flow

Production uses an OIDC-compatible API boundary: with `DEV_AUTH_ENABLED=false`, requests must carry a
signed bearer token whose issuer and audience match configuration and whose signing key resolves from
`OIDC_JWKS_URL` or `OIDC_JWKS_JSON`. Optional `OIDC_GROUP_ROLE_MAP_JSON` maps enterprise groups to
server-side roles. Local development uses seeded identities passed through `x-dev-user`. With
`NEXT_PUBLIC_AUTH_MODE=oidc`, the frontend starts authorization-code flow with PKCE and stores the
short-lived access token in `sessionStorage`; server-managed refresh-token handling remains the next
identity-layer step.

## Failure Handling

State transitions are explicit. Provider operations use idempotency keys. Lifecycle jobs store payload, attempt count, and failure details. Privileged authorization failures produce audit events.
