# Provider Integrations

Provider behavior is implemented behind adapter contracts. Phase 1 uses mock adapters for Amazon Bedrock, Amazon SageMaker, Gemini Enterprise app, Gemini Enterprise Agent Platform, Microsoft Foundry, Azure OpenAI, and GitHub Copilot.

`PROVIDER_MODE=live` switches the registry to live adapter boundaries. Live configuration and
health checks report provider-specific readiness from safe environment metadata such as
`AWS_REGION`, `AZURE_TENANT_ID`, `GOOGLE_CLOUD_PROJECT`, and `GITHUB_ORG`, plus the required SDK
module availability for AWS, Azure, Azure OpenAI, Microsoft Graph, Google Cloud, and GitHub.
Mutating live operations still fail closed unless `PROVIDER_LIVE_OPERATIONS_ENABLED=true`. When the
flag is enabled, live adapters return provider-specific least-privilege operation profiles, resource
identifiers, and audit metadata for assignments, suspension, restore, deprovisioning, usage, and
artifact archival.

## Google Provider Boundaries

Google's current naming separates the employee-facing Gemini Enterprise app from the developer
platform now branded Gemini Enterprise Agent Platform, formerly Vertex AI Platform. The control
plane models those as distinct provider IDs because the access operation and governance evidence are
different:

| Provider ID | Display Name | Control-Plane Access Profile | Scope | Subject |
| --- | --- | --- | --- | --- |
| `google_gemini_enterprise_app` | Gemini Enterprise app | `google_gemini_enterprise_app_assignment` | `gemini-enterprise-user-access` | Google group |
| `google_gemini_enterprise_agent_platform` | Gemini Enterprise Agent Platform | `google_project_iam_binding` | `roles/aiplatform.user` | Google group |

Legacy request payloads and persisted JSON values using `google_gemini_enterprise` or
`google_vertex_ai` are normalized to the current provider IDs. The Agent Platform readiness check
still verifies `google.cloud.aiplatform` because the Python SDK package name remains current even
though the product branding changed.

The API accepts those legacy aliases during the transition and returns only canonical provider IDs
in new responses. Legacy alias normalization emits a structured `provider.legacy_alias_normalized`
warning so operators can find stale clients without adding noisy warnings to the ordinary dashboard
flow.

The Alembic migration rewrites provider strings in assignments, resources, usage, cost, audit,
credential, health-check, lifecycle-job, incident, and request JSON records. PostgreSQL enum values
for `request_services.provider` are expanded append-only before stored values are rewritten; SQLite
uses the existing string-compatible enum storage. Downgrade maps current values back to the previous
names, but PostgreSQL enum labels are not removed because removing enum values is unsafe in normal
append-only migration history.

## Provider Maturity Matrix

| Provider | Mock Mode | Live Readiness Check | Guarded Live Operation Profile | Notes |
| --- | --- | --- | --- | --- |
| Amazon Bedrock | Complete | `boto3`, `AWS_REGION` | Permission-set style Bedrock invocation scope | Mutating API calls remain feature-flagged. |
| Amazon SageMaker | Complete | `boto3`, `AWS_REGION` | IAM role policy attachment for endpoint invocation | Mutating API calls remain feature-flagged. |
| Gemini Enterprise app | Complete | Google Cloud Resource Manager, `GOOGLE_CLOUD_PROJECT` | App assignment to a Google group | Models employee app access separately from Agent Platform project IAM. |
| Gemini Enterprise Agent Platform | Complete | Google Cloud Resource Manager, `google.cloud.aiplatform`, `GOOGLE_CLOUD_PROJECT` | Project IAM binding with `roles/aiplatform.user` | Product was formerly Vertex AI Platform. |
| Microsoft Foundry | Complete | Azure Identity, Microsoft Graph, `AZURE_TENANT_ID` | Azure role assignment | Mutating API calls remain feature-flagged. |
| Azure OpenAI | Complete | Azure Identity, OpenAI SDK, `AZURE_TENANT_ID` | Cognitive Services OpenAI User role assignment | Mutating API calls remain feature-flagged. |
| GitHub Copilot | Complete | PyGithub, `GITHUB_ORG` | Copilot Business seat assignment | Mutating API calls remain feature-flagged. |

## Signed Provider Webhooks

Provider callbacks are accepted at `/webhooks/provider-events` only when they include
`x-provider-timestamp` and `x-provider-signature`. The signature is `sha256=<hmac>` over
`timestamp.body` using `PROVIDER_WEBHOOK_SECRET`, and timestamps must be within the replay window.
Accepted deliveries write `provider.webhook_received` audit evidence with provider and delivery
metadata.

## Failure Modes

- Retryable provider timeout.
- Permanent authorization failure.
- Delayed billing data.
- Partial deprovisioning.
- Artifact archival failure.

Each provider operation must return safe error details, avoid credential leakage, and write audit evidence.
