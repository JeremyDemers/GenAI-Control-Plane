# Interview Demo

Use this as the short presenter path for AI Access Control Center. The goal is to show the
interviewer a complete governance lifecycle, not every screen.

## Setup

```bash
make dev
```

Open `http://localhost:3000`.

If local ports are already busy, use the alternate-port command and open `http://localhost:3001`:

```bash
API_PORT=8010 WEB_PORT=3001 POSTGRES_PORT=55432 REDIS_PORT=56379 NEXT_PUBLIC_API_URL=http://localhost:8010 make dev
```

If Compose is not available, install native Podman Compose support:

```bash
sudo apt install podman-compose
```

## Opening Talk Track

This is a production-style internal control plane for temporary enterprise access to generative AI
platforms. The important design point is separation of concerns: the Next.js portal has no provider
logic, the FastAPI API owns policy/RBAC/audit state, and provider-specific behavior sits behind
adapter boundaries. Local mode uses seeded identities and mock provider operations so the full
workflow can be demonstrated safely.

## Five-Minute Path

1. Select `employee@example.local`.
2. Submit the seeded Amazon Bedrock and GitHub Copilot request.
3. Point out policy evaluation, approval path, notifications, requested budget, data class, and provider list.
4. Select `approver@example.local` and approve the manager step.
5. Select `cto@example.local` and approve final access.
6. Show the request becoming `ACTIVE`.
7. Select `admin@example.local`.
8. In Developer Controls, trigger 70%, 90%, and 100% budget thresholds.
9. Show spend, remaining budget, fresh usage/cost evidence, automatic suspension, incident creation, and notifications.
10. Resolve the incident and restore the assignment.
11. Run the expiration-warning scan and show the requester/admin notification plus audit evidence.
12. Select `employee@example.local`, request a one-week extension, then approve it as `cto@example.local`.
13. Select `admin@example.local`, force expiration, then show archive/deprovision evidence.
14. Select `auditor@example.local`, show audit trail, role-change/provisioning evidence, adoption reporting, and export CSV evidence.

## What To Emphasize

- **Enterprise auth shape:** local seeded identities mirror OIDC roles; API validates bearer tokens in OIDC mode and keeps refresh tokens server-side.
- **RBAC and separation of duties:** employees request, approvers decide, admins operate, auditors read/export evidence.
- **Policy governance:** requests retain the policy version used during evaluation.
- **Temporary access:** assignments have expiration, extension workflow, forced expiration, archive, and deprovisioning.
- **Expiration governance:** active assignments nearing their end date produce requester/admin notifications and audit evidence.
- **Cost control:** usage/cost records drive 70%, 90%, and 100% threshold behavior, including suspension and incident evidence.
- **Adoption governance:** privileged users can review adoption by department, provider, and project activity, then export the report with audit evidence.
- **Provider boundary:** mock and live adapters share the same contract; live mutating operations are feature-flagged and fail closed.
- **Auditability:** lifecycle jobs, approvals, provider evidence, incident resolution, exports, and retention actions produce audit records.
- **Delivery readiness:** Docker Compose, health checks, Alembic, CI, backend/frontend tests, Playwright demo flow, and Terraform validation are wired.

## Optional Deep Dives

- Show `/docs` on the API for OpenAPI if they ask about backend surface area.
- Show `docs/architecture.md`, `docs/security-model.md`, or `docs/threat-model.md` if they ask about design.
- Mention `docs/dependency-audit.md` if dependency/security posture comes up.
- Run the automated demo check if there is time:

```bash
make e2e
```
