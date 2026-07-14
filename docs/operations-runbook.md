# Operations Runbook

## Failed Provisioning

Review lifecycle job failure details, provider health, and audit events. Retry with the same idempotency key when the error is retryable.
Admins can inspect recent jobs at `/lifecycle-jobs` and request a retry for queued or failed jobs at
`/lifecycle-jobs/{job_id}/retry`.

## Failed Deprovisioning

Suspend assignments first, collect final usage and cost data, retry deprovisioning, and preserve provider evidence.

## Provider Outage

Mark provider health degraded, pause new provisioning for that provider, notify platform administrators, and retry queued jobs with exponential backoff.

## Budget Delay

Show data freshness timestamps, distinguish estimated and provider-reported cost, and reconcile delayed records before final closure.

## Emergency Suspension

Platform administrators can suspend assignments. The action must create audit events and notify project owners.

## Notifications

Users can review their own notifications at `/notifications`. The local portal shows a notification
inbox for request submission, approval handoffs, provisioning, budget thresholds, suspension, restore,
and closure. Reading another user's notification returns `404`.

## Audit Export

Security auditors can export the latest 1,000 audit events as CSV at `/audit-events/export`.
The export action writes an `audit.exported` audit event with row count and correlation ID metadata.

## Executive Reporting

CTOs can review executive rollups at `/reports/executive`. The report summarizes request status,
active and suspended projects, total budget, current spend, remaining budget, provider spend, token
usage, and cost-center spend.

## Local Demo Lifecycle

In local mode, the developer panel can simulate budget warning, critical, and enforcement thresholds.
Enforcement suspends the assignment, creates an incident, and notifies the requester and platform
administrators. Restore and forced expiration actions use the mock provider adapter, write audit events,
archive artifacts locally, deprovision access, notify participants, and close the request.

## Credential Rotation

Rotate external credentials through the secret manager, validate provider configuration, and record the rotation evidence.
