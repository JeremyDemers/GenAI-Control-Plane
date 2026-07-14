# Threat Model

Method: STRIDE.

## Spoofing

Threats include stolen access tokens and forged webhook calls. Mitigations include OIDC with PKCE, short-lived tokens, signed webhook validation, and local dev auth disabled outside local environments.

## Tampering

Threats include approval bypass, audit-log modification, and job replay. Mitigations include explicit state transitions, append-only audit behavior, idempotency keys, and server-side authorization.

## Repudiation

Threats include users denying approval, suspension, or provider actions. Mitigations include structured audit events with actor, target, correlation ID, timestamps, and decision comments.

## Information Disclosure

Threats include prompt leakage, provider credential leakage, and cross-project data access. Mitigations include no prompt or response logging by default, credential isolation, redaction, and project-scoped authorization.

## Denial of Service

Threats include expensive request floods, queue pressure, and provider outage. Mitigations include rate limiting, job backoff, provider health checks, and incident workflows.

## Elevation of Privilege

Threats include role escalation, excessive cloud permissions, and approval-step impersonation. Mitigations include deny-by-default RBAC, separation of duties, least-privilege provider adapters, and auditable privileged failures.

