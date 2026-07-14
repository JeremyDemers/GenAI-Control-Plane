# Provider Integrations

Provider behavior is implemented behind adapter contracts. Phase 1 uses mock adapters for Amazon Bedrock, Amazon SageMaker, Google Gemini Enterprise, Google Vertex AI, Microsoft Foundry, Azure OpenAI, and GitHub Copilot.

Live mode will add provider-specific read-only validation first, then safe assignment operations behind feature flags.

## Failure Modes

- Retryable provider timeout.
- Permanent authorization failure.
- Delayed billing data.
- Partial deprovisioning.
- Artifact archival failure.

Each provider operation must return safe error details, avoid credential leakage, and write audit evidence.

