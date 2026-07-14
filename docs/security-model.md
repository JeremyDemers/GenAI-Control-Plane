# Security Model

## Trust Boundaries

- Browser to API boundary: all authorization is enforced on the server.
- API to provider boundary: provider credentials never reach the browser.
- API to database boundary: SQLAlchemy parameterization is used instead of string-built SQL.
- Worker boundary: durable jobs use idempotency keys and audit events.

## Identity

Production identity is OIDC-compatible and intended for Microsoft Entra ID. Local identity is deterministic and limited to seeded demo users.

## Authorization

The API denies by default. Route dependencies require permissions, and service-level checks are used for workflow ownership and assignment. Auditor roles can read audit data but cannot mutate operational records.

## Audit Logging

Audit events capture actor, target, request, project, provider, action, result, reason, correlation ID, and metadata. The application does not expose update or delete operations for audit events.

## Observability

The API emits structured JSON access logs with correlation and trace IDs. Incoming W3C `traceparent`
headers are propagated to `x-trace-id` response headers, and middleware-generated correlation IDs are
shared with authorization and workflow audit events.

## Abuse Controls

Local/demo API rate limiting is enforced in middleware and returns `429` with correlation, trace, and
rate-limit headers. Production deployments should move the same policy to a shared Redis or gateway
limiter for multi-instance consistency.

## Secrets

Real provider credentials and webhook signing secrets must be stored outside source control,
preferably in a cloud secret manager. `.env.example` contains only non-secret defaults and
placeholder local values.

## Data Retention

Artifact archives include retention expiration. Future lifecycle jobs will enforce retention policies and preserve deprovisioning evidence.
