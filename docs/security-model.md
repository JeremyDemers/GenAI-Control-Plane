# Security Model

## Trust Boundaries

- Browser to API boundary: all authorization is enforced on the server.
- API to provider boundary: provider credentials never reach the browser.
- API to database boundary: SQLAlchemy parameterization is used instead of string-built SQL.
- Worker boundary: durable jobs use idempotency keys and audit events.

## Identity

Production identity is OIDC-compatible and intended for Microsoft Entra ID. With
`DEV_AUTH_ENABLED=false`, the API rejects local development headers and validates signed bearer
tokens against configured issuer, audience, allowed algorithms, and a JWKS URL/static JWKS. Local
identity is deterministic and limited to seeded demo users while `DEV_AUTH_ENABLED=true`. When
`OIDC_GROUP_ROLE_MAP_JSON` is configured, mapped OIDC group claims replace the user's application
roles and produce `identity.roles_synchronized` audit evidence.

Microsoft login uses authorization-code flow with PKCE in the browser, server-side code exchange,
and HttpOnly refresh-token session cookies. The browser stores only short-lived access tokens; client
secrets remain on the API side.
Optional OIDC auto-provisioning is disabled by default; when enabled, new Microsoft-authenticated
users are created with a configured default role before group mapping is applied.

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

Artifact archives include retention expiration. The archive retention lifecycle job purges expired
archive locations while preserving checksums and audit evidence for deprovisioning review.
