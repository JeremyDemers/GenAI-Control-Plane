# Operations Runbook

## Failed Provisioning

Review lifecycle job failure details, provider health, and audit events. Retry with the same idempotency key when the error is retryable.

## Failed Deprovisioning

Suspend assignments first, collect final usage and cost data, retry deprovisioning, and preserve provider evidence.

## Provider Outage

Mark provider health degraded, pause new provisioning for that provider, notify platform administrators, and retry queued jobs with exponential backoff.

## Budget Delay

Show data freshness timestamps, distinguish estimated and provider-reported cost, and reconcile delayed records before final closure.

## Emergency Suspension

Platform administrators can suspend assignments. The action must create audit events and notify project owners.

## Local Demo Lifecycle

In local mode, the developer panel can simulate budget warning, critical, and enforcement thresholds.
Enforcement suspends the assignment and creates an incident. Restore and forced expiration actions use
the mock provider adapter, write audit events, archive artifacts locally, deprovision access, and close
the request.

## Credential Rotation

Rotate external credentials through the secret manager, validate provider configuration, and record the rotation evidence.
