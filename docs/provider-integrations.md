# Provider Integrations

Provider behavior is implemented behind adapter contracts. Phase 1 uses mock adapters for Amazon Bedrock, Amazon SageMaker, Google Gemini Enterprise, Google Vertex AI, Microsoft Foundry, Azure OpenAI, and GitHub Copilot.

`PROVIDER_MODE=live` switches the registry to live adapter boundaries. Live configuration and
health checks report provider-specific readiness from safe environment metadata such as
`AWS_REGION`, `AZURE_TENANT_ID`, `GOOGLE_CLOUD_PROJECT`, and `GITHUB_ORG`. Mutating live
operations fail closed unless `PROVIDER_LIVE_OPERATIONS_ENABLED=true`, and the concrete SDK
implementations still need to be installed before real provider changes are allowed.

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
