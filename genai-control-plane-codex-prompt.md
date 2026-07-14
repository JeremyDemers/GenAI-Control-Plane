# CODEX Build Prompt: GenAI Control Plane

## Project Name

**Repository name:** `genai-control-plane`  
**Product name:** **AI Access Control Center**

## Mission

Build a production-style internal enterprise web application that allows approved employees to request, receive, use, monitor, and automatically lose temporary access to generative AI platforms in a secure and governed way.

The application must demonstrate the core capabilities expected from a senior full-stack engineer building a multi-cloud AI governance platform:

- Enterprise authentication
- SSO-compatible architecture
- Role-based access control
- Approval workflows
- Multi-cloud provisioning
- Usage monitoring
- Cost governance
- Temporary access
- Automatic expiration
- Artifact archival
- Audit logging
- CI/CD
- Testing
- Documentation
- Deployment readiness

The final application should be suitable for a technical interview demonstration and portfolio presentation.

---

# 1. Product Summary

AI Access Control Center is a secure internal portal through which employees request temporary access to approved generative AI services.

The system must:

1. Authenticate users through an enterprise-compatible identity provider.
2. Apply role-based access controls.
3. Collect AI access requests.
4. Evaluate each request against configurable governance policies.
5. Route requests through manager, security, and CTO approval steps.
6. Provision temporary access through provider adapters.
7. Track usage and cost.
8. Enforce configurable spending limits.
9. Warn users when access or budget is nearing expiration.
10. Suspend or deprovision access automatically.
11. Archive project metadata and artifacts.
12. Preserve a complete audit history.

The architecture must separate the application control plane from cloud-specific provider integrations.

---

# 2. Target Technology Stack

## Frontend

Use:

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query
- React Hook Form
- Zod
- Recharts
- Playwright
- Vitest

## Backend

Use:

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic
- PostgreSQL
- Redis
- Celery or Dramatiq
- Pytest
- Ruff
- MyPy
- OpenTelemetry-compatible observability
- Structured JSON logging

## Provider SDKs

Prepare integration boundaries for:

- AWS SDK for Python, `boto3`
- Microsoft Azure SDKs
- Microsoft Graph
- Google Cloud client libraries
- GitHub REST and GraphQL APIs

## Infrastructure

Use:

- Docker
- Docker Compose
- Terraform
- GitHub Actions
- PostgreSQL
- Redis
- Optional deployment to AWS ECS/Fargate, Azure Container Apps, or a comparable container platform

---

# 3. High-Level Architecture

Use a modular control-plane architecture.

```text
┌──────────────────────────────────────────────────────────┐
│                    Next.js Web Portal                    │
│ Employee │ Approver │ Administrator │ Auditor dashboards │
└───────────────────────────┬──────────────────────────────┘
                            │
                            │ OIDC access token
                            ▼
┌──────────────────────────────────────────────────────────┐
│                       FastAPI API                        │
│ Auth │ RBAC │ Requests │ Policies │ Reports │ Audit      │
└───────┬───────────┬───────────┬───────────┬────────────┘
        │           │           │           │
        ▼           ▼           ▼           ▼
 PostgreSQL      Redis       Audit Store   Notifications
                    │
                    ▼
          ┌──────────────────────┐
          │ Provisioning Workers │
          └────┬──────┬──────┬──┘
               │      │      │
          ┌────▼─┐ ┌──▼───┐ ┌▼──────────┐
          │ AWS  │ │Azure │ │Google Cloud│
          └────┬─┘ └──┬───┘ └┬──────────┘
               │      │      │
               └──────┼──────┘
                      ▼
                ┌──────────┐
                │ GitHub   │
                │ Copilot  │
                └──────────┘
```

The web application must never contain cloud provider logic directly.

All provider-specific behavior must be implemented through provider adapters.

---

# 4. Required User Roles

Implement the following roles.

## Employee

Can:

- Sign in
- Submit access requests
- View personal requests
- View assigned projects
- View usage and budget data
- Request extensions
- View alerts
- Cancel requests that are still pending

## Project Owner

Can:

- View project members
- Review project-level usage
- View project budget
- Request new project members
- Request project extension
- Request project reassignment
- View project audit history

## Approver

Can:

- Review assigned approval tasks
- Approve requests
- Reject requests
- Request additional information
- Add approval comments

## Security Reviewer

Can:

- Review requests involving sensitive data
- Approve or reject security-sensitive requests
- View policy evaluation results
- View security-related audit events

## Platform Administrator

Can:

- View all projects and requests
- Manage policies
- Trigger provisioning
- Retry failed jobs
- Suspend assignments
- Restore assignments
- Deprovision assignments
- View provider health
- Manage integration configuration

## Security Auditor

Can:

- View all audit records
- Export audit reports
- View approval history
- View role changes
- View provisioning and deprovisioning evidence
- Cannot modify operational data

## CTO

Can:

- Approve high-cost or high-risk requests
- Review organization-level spending
- View executive reports
- Suspend projects
- Override approval decisions with mandatory justification

---

# 5. Authentication and Authorization

Implement enterprise-compatible authentication using OIDC.

The production architecture must support Microsoft Entra ID.

For local development, provide a development identity provider or mock authentication mode.

Seed the following development users:

```text
employee@example.local
owner@example.local
approver@example.local
security@example.local
admin@example.local
auditor@example.local
cto@example.local
```

Each development user must be assigned the corresponding application role.

Authorization requirements:

- Deny access by default.
- Check authorization on the server for every protected endpoint.
- Never rely solely on frontend role checks.
- Use route-level and service-level authorization.
- Add tests proving that unauthorized users cannot access protected resources.
- Record privileged authorization failures in the audit log.

---

# 6. Access Request Form

Create a request form that captures:

- Project name
- Business justification
- Project sponsor
- Cost center
- Requested start date
- Requested expiration date
- Requested budget
- Currency
- Requested AI providers
- Requested models or services
- Expected number of users
- Requested collaborators
- Data classification
- Whether personally identifiable information will be used
- Whether confidential data will be used
- Whether regulated data will be used
- Whether proprietary source code will be used
- Expected artifacts
- Expected usage pattern
- Estimated monthly token or request volume
- Additional notes

Supported providers:

- Amazon Bedrock
- Amazon SageMaker
- Google Gemini Enterprise
- Google Vertex AI
- Microsoft Foundry
- Azure OpenAI
- GitHub Copilot

The form must validate all inputs using both frontend and backend validation.

---

# 7. Request State Machine

Implement the following states:

```text
DRAFT
SUBMITTED
AWAITING_MANAGER_APPROVAL
AWAITING_SECURITY_REVIEW
AWAITING_CTO_APPROVAL
APPROVED
PROVISIONING
ACTIVE
EXPIRING_SOON
SUSPENDED
EXPIRED
ARCHIVING
CLOSED
REJECTED
CANCELLED
PROVISIONING_FAILED
DEPROVISIONING_FAILED
```

State transitions must be explicit and validated.

Do not allow arbitrary state changes.

Create a state transition service with unit tests.

Example flow:

```text
DRAFT
  -> SUBMITTED
  -> AWAITING_MANAGER_APPROVAL
  -> AWAITING_SECURITY_REVIEW
  -> AWAITING_CTO_APPROVAL
  -> APPROVED
  -> PROVISIONING
  -> ACTIVE
  -> EXPIRING_SOON
  -> EXPIRED
  -> ARCHIVING
  -> CLOSED
```

Alternative branches must support:

- Rejection
- Cancellation
- Suspension
- Provisioning failure
- Retry
- Extension
- Reactivation

---

# 8. Policy Engine

Create a versioned, configurable policy engine.

Policies must determine:

- Required approval steps
- Maximum access duration
- Maximum budget
- Allowed providers
- Allowed models
- Allowed data classifications
- Whether security review is required
- Whether CTO approval is required
- Budget warning thresholds
- Enforcement actions
- Artifact retention periods
- Extension limits
- Whether project reassignment is allowed

Example policy:

```yaml
name: standard-ai-sandbox
version: 1
maximum_duration_days: 30
maximum_budget_usd: 1000

approval_rules:
  require_manager_approval: true
  require_security_review_for:
    - confidential
    - regulated
  require_cto_approval_when:
    requested_budget_greater_than: 500
    high_risk_provider_requested: true

budget:
  warning_percent: 70
  critical_percent: 90
  enforcement_percent: 100

actions:
  warning:
    - notify_requester
    - notify_project_owner

  critical:
    - notify_platform_admin
    - restrict_high_cost_models

  enforcement:
    - suspend_access
    - revoke_credentials
    - create_incident

prohibited_data_classes:
  - restricted
```

Store policy versions.

Every request must retain the policy version used during evaluation.

Create policy evaluation records showing:

- Policy evaluated
- Rules triggered
- Approval path selected
- Restrictions applied
- Final decision
- Evaluation timestamp

---

# 9. Provider Adapter Interface

Create a common provider adapter contract.

Example:

```python
from typing import Protocol

class AIProviderAdapter(Protocol):
    async def provision_access(self, request):
        ...

    async def suspend_access(self, assignment_id: str):
        ...

    async def restore_access(self, assignment_id: str):
        ...

    async def deprovision_access(self, assignment_id: str):
        ...

    async def collect_usage(self, assignment_id: str, start_at, end_at):
        ...

    async def archive_artifacts(self, assignment_id: str):
        ...

    async def validate_configuration(self):
        ...

    async def health_check(self):
        ...
```

Provider operations must:

- Be idempotent
- Use idempotency keys
- Support retries
- Distinguish retryable and permanent failures
- Produce audit events
- Return provider-generated resource identifiers
- Preserve provider error details safely
- Avoid leaking credentials or secrets into logs

---

# 10. AWS Adapter

Create an AWS adapter.

The adapter should model:

- IAM role assignment
- AWS Identity Center permission assignment
- Bedrock model access
- SageMaker project or studio access
- AWS account or project association
- Cost center tags
- Expiration tags
- AWS Budgets
- CloudWatch metrics
- Cost and Usage Report imports
- CloudTrail references

Implement two modes:

## Mock Mode

Must be fully functional for demonstrations.

Simulate:

- Provisioning delays
- AWS resource identifiers
- Access success
- Access failure
- Usage accumulation
- Cost accumulation
- Budget alerts
- Suspension
- Deprovisioning
- Artifact archival

## Live Mode

Create integration boundaries and configuration for real AWS credentials.

The live mode does not need to create dangerous or expensive resources by default.

Use safe feature flags.

---

# 11. Azure and Microsoft Adapter

Create an Azure/Microsoft adapter.

Model:

- Microsoft Entra group membership
- Azure role assignments
- Azure subscription or resource-group access
- Microsoft Foundry project access
- Azure OpenAI deployment access
- Azure Cost Management
- Azure budgets
- Microsoft Graph interactions
- GitHub Copilot assignment through a separate GitHub adapter

Provide mock and live-capable modes.

---

# 12. Google Cloud Adapter

Create a Google Cloud adapter.

Model:

- Google Cloud project assignment
- IAM roles
- Gemini Enterprise access
- Vertex AI access
- Billing account association
- Cloud Billing budgets
- Quotas
- Project labels
- Suspension
- Deprovisioning
- Artifact archival

Provide mock and live-capable modes.

---

# 13. GitHub Copilot Adapter

Create a GitHub adapter.

Model:

- GitHub organization membership
- Team membership
- Copilot seat assignment
- Copilot seat removal
- Usage metric retrieval
- Adoption reporting
- User activity reporting
- Project-level reporting based on team membership

Provide mock and live-capable modes.

---

# 14. Database Model

Create SQLAlchemy models and Alembic migrations for at least:

```text
users
roles
user_roles
projects
project_members
access_requests
request_services
approval_steps
approval_decisions
provider_assignments
provider_resources
usage_records
cost_records
budgets
budget_thresholds
policy_definitions
policy_versions
policy_evaluations
notifications
artifact_archives
lifecycle_jobs
audit_events
integration_credentials
provider_health_checks
incidents
extension_requests
reassignment_requests
```

Important `access_requests` fields:

```text
id
requester_id
project_id
business_justification
data_classification
risk_level
requested_start_at
requested_end_at
requested_budget
currency
status
policy_version_id
submitted_at
approved_at
provisioned_at
expires_at
closed_at
created_at
updated_at
```

Important `audit_events` fields:

```text
id
event_type
actor_user_id
actor_type
target_type
target_id
request_id
project_id
provider
action
result
reason
correlation_id
ip_address
user_agent
metadata_json
created_at
```

Audit events must be append-only from the application perspective.

---

# 15. Workflow Automation

Use asynchronous jobs for:

- Provisioning
- Usage collection
- Cost collection
- Budget evaluation
- Notifications
- Expiration warnings
- Suspension
- Deprovisioning
- Artifact archival
- Provider health checks
- Failed job retries
- Reconciliation

Create a lifecycle scheduler that periodically performs:

```text
1. Find assignments approaching expiration.
2. Send seven-day warnings.
3. Send three-day warnings.
4. Send one-day warnings.
5. Find assignments that have expired.
6. Suspend expired assignments.
7. Collect final usage and cost data.
8. Archive project metadata.
9. Archive configured artifacts.
10. Remove provider access.
11. Verify that access was removed.
12. Store deprovisioning evidence.
13. Mark the request and project closed.
```

Each job must:

- Have a unique job identifier
- Store status
- Store attempt count
- Store failure information
- Use exponential backoff
- Support manual retry
- Produce audit events
- Be idempotent

---

# 16. Budget and Cost Governance

Support budget limits at:

- Organization level
- Provider level
- Project level
- User level
- Assignment level

Create thresholds:

- Warning at 70%
- Critical at 90%
- Enforcement at 100%

Make threshold values configurable.

At warning:

- Notify requester
- Notify project owner

At critical:

- Notify administrators
- Highlight the project on dashboards
- Optionally restrict expensive models

At enforcement:

- Suspend provider assignment
- Revoke temporary credentials
- Disable project access
- Create an incident
- Notify administrators and project owners

Do not assume that provider billing data is real-time.

The system must distinguish:

- Estimated cost
- Reported provider cost
- Reconciled cost
- Delayed billing data

Show data freshness timestamps on dashboards.

---

# 17. Dashboards

## Employee Dashboard

Show:

- Active projects
- Pending requests
- Request status
- Remaining budget
- Expiration countdown
- Current usage
- Recent alerts
- Extension requests
- Available providers and services

## Project Dashboard

Show:

- Total cost
- Cost by provider
- Cost by user
- Usage by provider
- Token usage
- Request volume
- Daily cost trend
- Weekly cost trend
- Budget utilization
- Forecasted end-of-period cost
- Active members
- Provisioned resources
- Expiration date
- Recent audit events

## Approver Dashboard

Show:

- Pending approvals
- Request risk level
- Requested budget
- Data classification
- Triggered policy rules
- Approval history
- Approve, reject, and request-information actions

## Administrator Dashboard

Show:

- Total active users
- Active projects
- Pending approvals
- Provisioning failures
- Deprovisioning failures
- Expiring assignments
- Suspended assignments
- Spending by cloud
- Projects near limits
- Provider health
- Worker queue health
- Recent incidents

## Auditor Dashboard

Show:

- Sign-in events
- Approval history
- Role changes
- Policy evaluations
- Provisioning events
- Suspension events
- Deprovisioning evidence
- Artifact archival records
- Budget enforcement actions
- Exportable audit report

## Executive Dashboard

Show:

- Organization-wide spend
- Spend by provider
- Spend by department or cost center
- Active project count
- Active user count
- Approval turnaround time
- Budget incidents
- Provider adoption
- Expiring projects
- High-risk requests

---

# 18. Project Reassignment

Support project ownership reassignment.

Workflow:

```text
1. Current owner requests reassignment.
2. New owner is selected.
3. New owner accepts.
4. Approval is required.
5. Provider assignments are updated.
6. Project ownership is changed.
7. Existing audit history is preserved.
8. Both owners and administrators are notified.
```

Do not overwrite historical owner information.

Create ownership history records.

---

# 19. Artifact Archival

Create an artifact archival abstraction.

Artifacts may include:

- Project metadata
- Provider resource inventory
- Usage reports
- Cost reports
- Approval records
- Audit exports
- User-uploaded project files
- Model evaluation results
- Prompt templates
- Configuration files

Mock archival can store files locally or in an S3-compatible development service.

Production architecture should support:

- Amazon S3
- Azure Blob Storage
- Google Cloud Storage

Every archive must include:

- Archive identifier
- Project identifier
- Assignment identifier
- Storage provider
- Storage location
- Checksum
- Archive timestamp
- Retention expiration
- Created-by job identifier

---

# 20. Notifications

Create a notification service abstraction.

Support:

- In-app notifications
- Email adapter
- Optional Microsoft Teams adapter
- Optional Slack adapter

Notification events:

- Request submitted
- Approval required
- Request approved
- Request rejected
- Provisioning started
- Provisioning completed
- Provisioning failed
- Budget warning
- Budget critical
- Access suspended
- Expiration warning
- Access expired
- Deprovisioning completed
- Archival completed
- Extension approved
- Project reassigned

Provide a local development inbox or notification log.

---

# 21. Security Requirements

Implement and document:

- OIDC authorization-code flow with PKCE
- Short-lived access tokens
- Secure refresh-token handling
- Server-side RBAC enforcement
- Least privilege
- Separation of duties
- Secure cookies
- CSRF protection where applicable
- Content Security Policy
- Rate limiting
- Input validation
- Output encoding
- SQL injection protection
- Secrets stored outside source control
- Encryption in transit
- Encryption at rest
- Structured security logging
- Dependency scanning
- Container scanning
- Audit logging
- Sensitive-data redaction
- No prompt or response logging by default
- Credential rotation support
- Signed webhook validation
- Idempotency controls
- Break-glass access procedure
- Data-retention policies
- Session timeout
- Account lockout or abuse controls

Create a threat model.

Include threats such as:

- Privilege escalation
- Approval bypass
- Excessive permissions
- Stolen access tokens
- Leaked cloud credentials
- Unauthorized provider access
- Cost abuse
- Prompt data leakage
- Audit-log tampering
- Job replay
- Webhook spoofing
- Cross-project data access
- Insecure artifact storage
- Improper deprovisioning

Document mitigations.

---

# 22. API Requirements

Create REST endpoints grouped by domain.

Suggested routes:

```text
/auth
/users
/roles
/projects
/project-members
/access-requests
/approvals
/policies
/provider-assignments
/providers
/usage
/costs
/budgets
/notifications
/artifacts
/lifecycle-jobs
/audit-events
/incidents
/extensions
/reassignments
/admin
/health
```

Provide OpenAPI documentation.

Use consistent:

- Pagination
- Filtering
- Sorting
- Error responses
- Correlation IDs
- Validation responses
- Authorization errors

Use an error format such as:

```json
{
  "error": {
    "code": "REQUEST_NOT_APPROVABLE",
    "message": "The request is not currently awaiting approval.",
    "correlation_id": "..."
  }
}
```

---

# 23. Observability

Implement:

- Structured JSON logs
- Correlation IDs
- Request tracing
- Worker job tracing
- Provider operation metrics
- API latency metrics
- Error-rate metrics
- Provisioning duration metrics
- Approval duration metrics
- Budget enforcement metrics
- Provider health metrics

Provide health endpoints:

```text
/health/live
/health/ready
/health/providers
```

Never write secrets, access tokens, prompts, or model responses to logs.

---

# 24. Testing Requirements

Create:

## Backend Unit Tests

Test:

- State transitions
- Policy evaluations
- RBAC
- Budget thresholds
- Lifecycle calculations
- Provider adapter behavior
- Idempotency
- Retry logic
- Audit event generation

## Backend Integration Tests

Test:

- Database operations
- API endpoints
- Approval workflow
- Provisioning workflow
- Expiration workflow
- Archival workflow
- Budget enforcement workflow

## Frontend Tests

Test:

- Request form validation
- Role-based navigation
- Approval interactions
- Dashboard rendering
- Error handling
- Loading states
- Accessibility

## End-to-End Tests

Use Playwright.

Create end-to-end scenarios:

1. Employee submits request.
2. Manager approves.
3. Security reviewer approves.
4. CTO approves.
5. Provisioning completes.
6. Usage is generated.
7. Budget threshold is reached.
8. Access is suspended.
9. Administrator restores access.
10. Project expires.
11. Artifacts are archived.
12. Access is removed.
13. Auditor verifies the complete history.

Target meaningful test coverage, not artificial coverage.

---

# 25. CI/CD

Create GitHub Actions workflows for:

- Backend linting
- Backend type checking
- Backend tests
- Frontend linting
- Frontend type checking
- Frontend tests
- Playwright tests
- Docker image build
- Dependency scanning
- Secret scanning
- Container scanning
- Terraform validation
- Terraform formatting
- Migration validation

Do not deploy automatically to production.

Create separate workflows or environments for:

- Pull request validation
- Development deployment
- Production deployment approval

---

# 26. Local Development

Create a Docker Compose environment containing:

- Next.js frontend
- FastAPI backend
- PostgreSQL
- Redis
- Worker
- Scheduler
- Optional local object storage
- Optional local email testing service

Provide commands such as:

```bash
make setup
make dev
make test
make lint
make typecheck
make migrate
make seed
make reset
make e2e
```

Create a `.env.example`.

Never commit real credentials.

---

# 27. Repository Structure

Use this structure:

```text
genai-control-plane/
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── tests/
│   └── api/
│       ├── app/
│       │   ├── api/
│       │   ├── auth/
│       │   ├── core/
│       │   ├── domain/
│       │   ├── models/
│       │   ├── policies/
│       │   ├── providers/
│       │   │   ├── aws/
│       │   │   ├── azure/
│       │   │   ├── google/
│       │   │   ├── github/
│       │   │   └── mock/
│       │   ├── repositories/
│       │   ├── services/
│       │   ├── workers/
│       │   └── observability/
│       └── tests/
├── packages/
│   ├── contracts/
│   └── ui/
├── infrastructure/
│   ├── terraform/
│   ├── docker/
│   └── policies/
├── docs/
│   ├── architecture.md
│   ├── security-model.md
│   ├── threat-model.md
│   ├── provider-integrations.md
│   ├── deployment.md
│   ├── operations-runbook.md
│   ├── interview-demo.md
│   └── decisions/
├── scripts/
├── .github/
│   └── workflows/
├── docker-compose.yml
├── Makefile
├── .env.example
├── README.md
└── LICENSE
```

---

# 28. Documentation

Create:

## README.md

Include:

- Product overview
- Screenshots
- Architecture summary
- Local setup
- Demo users
- Key features
- Security summary
- Testing instructions
- Deployment summary
- Known limitations
- Roadmap

## architecture.md

Include:

- System context
- Container architecture
- Component architecture
- Data flow
- Provider adapter pattern
- Authentication flow
- Provisioning flow
- Usage ingestion flow
- Lifecycle flow
- Failure handling

## security-model.md

Include:

- Trust boundaries
- Identity model
- Authorization model
- Secrets handling
- Audit logging
- Data retention
- Incident response

## threat-model.md

Use STRIDE or a comparable methodology.

## provider-integrations.md

Document:

- AWS
- Azure
- Google Cloud
- GitHub
- Mock provider behavior
- Live mode configuration
- Permissions required
- Failure modes

## operations-runbook.md

Document:

- Failed provisioning
- Failed deprovisioning
- Provider outage
- Budget data delay
- Credential rotation
- Emergency suspension
- Queue failure
- Database recovery
- Audit export

## interview-demo.md

Create a step-by-step demo script.

---

# 29. Interview Demo Scenario

Build seeded demo data supporting this story:

1. Sign in as an employee.
2. Create a request for Amazon Bedrock and GitHub Copilot.
3. Request 14 days of access.
4. Request a budget of $100.
5. Select internal data classification.
6. Submit the request.
7. Show policy evaluation.
8. Sign in as approver.
9. Approve the request.
10. Sign in as CTO.
11. Approve final access.
12. Show asynchronous provisioning.
13. Display provider assignments.
14. Simulate usage.
15. Show cost increasing.
16. Trigger the 70% warning.
17. Trigger the 90% critical alert.
18. Trigger the 100% enforcement action.
19. Show automatic suspension.
20. Restore the assignment as an administrator.
21. Force the expiration date.
22. Run lifecycle processing.
23. Show artifact archival.
24. Show access removal.
25. Sign in as auditor.
26. Trace the entire lifecycle from request through closure.

Create a simple developer control panel for simulating:

- Time advancement
- Usage creation
- Cost creation
- Provider failure
- Budget threshold crossing
- Expiration
- Queue retry

The developer panel must only exist in local development mode.

---

# 30. Implementation Phases

Implement in phases.

## Phase 1: Foundation

- Initialize monorepo
- Configure frontend
- Configure backend
- Configure PostgreSQL
- Configure Redis
- Add Docker Compose
- Add code quality tools
- Add health checks

## Phase 2: Identity and RBAC

- Development authentication
- Entra-compatible OIDC structure
- Roles
- Permissions
- Authorization tests
- Role-based navigation

## Phase 3: Requests and Policies

- Access request form
- Request API
- State machine
- Policy engine
- Policy evaluation records
- Request dashboards

## Phase 4: Approval Workflow

- Approval tasks
- Manager approval
- Security approval
- CTO approval
- Rejection
- Additional-information flow
- Notifications

## Phase 5: Provider Framework

- Provider adapter contract
- Provider registry
- Mock provider
- Provisioning jobs
- Retry logic
- Idempotency
- Provider health

## Phase 6: AWS Integration

- AWS mock adapter
- Live-capable AWS adapter boundaries
- Bedrock assignment model
- SageMaker assignment model
- Cost and usage ingestion abstraction

## Phase 7: Azure, Google, and GitHub

- Mock adapters
- Live-capable integration boundaries
- Provider resource records
- Usage normalization
- Cost normalization

## Phase 8: Dashboards and Governance

- Employee dashboard
- Project dashboard
- Administrator dashboard
- Auditor dashboard
- Executive dashboard
- Budget thresholds
- Enforcement

## Phase 9: Lifecycle Management

- Expiration warnings
- Suspension
- Archival
- Deprovisioning
- Verification
- Closure
- Reassignment
- Extensions

## Phase 10: Hardening

- Security review
- Threat model
- Integration tests
- E2E tests
- Observability
- CI/CD
- Documentation
- Interview demo

---

# 31. Definition of Done

The project is complete when:

- A user can sign in.
- Roles restrict access correctly.
- An employee can submit an AI access request.
- The policy engine determines required approvals.
- Approvers can approve or reject requests.
- Approved requests create asynchronous provisioning jobs.
- Mock providers create provider assignments.
- Usage and cost data appear on dashboards.
- Budget thresholds generate warnings and enforcement.
- Access expires automatically.
- Artifacts are archived.
- Provider access is removed.
- Audit records trace the complete lifecycle.
- Automated tests cover critical workflows.
- Docker Compose starts the complete application.
- CI validates the project.
- Documentation explains the architecture and security model.
- The seeded interview demonstration works from beginning to end.

---

# 32. Engineering Standards

Follow these standards:

- Prefer clear, maintainable code over clever abstractions.
- Use strong typing.
- Keep domain logic out of controllers.
- Keep provider logic behind adapter interfaces.
- Use dependency injection where beneficial.
- Use repository and service layers where they improve separation.
- Use database transactions for state-changing workflows.
- Use idempotency for provisioning and deprovisioning.
- Never expose provider credentials to the frontend.
- Never log secrets.
- Never hard-code production credentials.
- Validate all external input.
- Write meaningful tests alongside features.
- Create architectural decision records for major choices.
- Keep commits small and focused.
- Do not create placeholder code without clearly marking it.
- Do not silently ignore failures.
- Fail securely.

---

# 33. Initial CODEX Instructions

Begin by:

1. Reviewing this entire specification.
2. Creating an implementation plan.
3. Creating the repository structure.
4. Creating `README.md`.
5. Creating `docs/architecture.md`.
6. Creating `docs/security-model.md`.
7. Creating `docs/threat-model.md`.
8. Creating the Docker Compose foundation.
9. Creating the FastAPI application.
10. Creating the Next.js application.
11. Creating PostgreSQL and Redis configuration.
12. Creating initial database models.
13. Creating development authentication.
14. Creating role-based authorization.
15. Creating seed users.
16. Creating health endpoints.
17. Creating baseline tests.
18. Creating Makefile commands.
19. Verifying that the complete development environment starts successfully.

After the foundation is working, continue phase by phase.

Do not attempt to implement the entire project in one uncontrolled change.

At the end of each phase:

- Run tests.
- Run linting.
- Run type checking.
- Update documentation.
- Record remaining work.
- Commit only when the phase is stable.

---

# 34. Expected Portfolio Positioning

The final project should demonstrate that the engineer can:

- Build secure enterprise web applications
- Integrate enterprise SSO
- Implement RBAC
- Design approval workflows
- Build multi-cloud abstractions
- Work with generative AI platforms
- Implement cloud cost governance
- Automate provisioning
- Manage temporary access
- Build dashboards
- Implement lifecycle automation
- Design CI/CD pipelines
- Apply enterprise security practices
- Produce professional technical documentation

The project should look like a credible enterprise reference implementation, not a tutorial application.
