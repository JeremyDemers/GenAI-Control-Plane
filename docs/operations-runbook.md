# Operations Runbook

## Failed Provisioning

Review lifecycle job failure details, provider health, and audit events. Retry with the same idempotency key when the error is retryable.
Admins can inspect recent jobs at `/lifecycle-jobs` and request a retry for queued or failed jobs at
`/lifecycle-jobs/{job_id}/retry`. Provider failure metadata is sanitized before persistence; secrets
and raw credential material must remain in the external secret manager or provider logs.

## Failed Deprovisioning

Suspend assignments first, collect final usage and cost data, retry deprovisioning, and preserve provider evidence.

## Provider Outage

Mark provider health degraded, pause new provisioning for that provider, notify platform administrators, and retry queued jobs with exponential backoff.
Provider health is available at `/providers/health`. Platform administrators, security auditors, and
CTOs can validate safe provider configuration metadata at `/providers/configuration`.

## Policy Versioning

Platform administrators can inspect policy versions at `/policies` and publish a new active standard
policy at `/policies/standard-ai-sandbox/versions`. Existing requests retain their evaluated
`policy_version_id`; newly submitted requests use the active policy version.

## Budget Delay

Show data freshness timestamps, distinguish estimated and provider-reported cost, and reconcile delayed records before final closure.

For Gemini Enterprise app assignments, treat seat/subscription allocation and user activity as the
primary evidence. Use labels such as `assigned_seat_cost`, `internally_allocated_cost`,
`provider_reported_subscription_cost`, `activity_count`, and `agent_invocation_count` when those
signals are available. Do not imply exact real-time per-user billing when the provider only supplies
subscription-level data.

For Gemini Enterprise Agent Platform assignments, tie usage and cost evidence to the governed
Google Cloud project and cost center. Continue distinguishing `estimated_cost`,
`provider_reported_cost`, `reconciled_cost`, and `data_freshness`; cloud billing exports may lag
operational activity.

## Usage, Cost, and Budget Evidence

Employees can review evidence for their own requests at `/provider-assignments`, `/usage`, `/costs`,
and `/budgets`. Project members can review evidence for their assigned projects through the same
endpoints and can list visible projects at `/projects`. Reviewers can review evidence for requests
assigned to their approval queue. Platform administrators, security auditors, and CTOs can review all
visible assignments, usage records, cost records, and budget summaries with freshness timestamps.

## Emergency Suspension

Platform administrators can suspend assignments. The action must create audit events and notify project owners.

## Incidents

Budget enforcement creates high-severity incidents. Platform administrators and auditors can review
incidents at `/incidents`; administrators can resolve incidents with a reason at
`/incidents/{incident_id}/resolve`, which emits `incident.resolved` audit evidence.

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
usage, and cost-center spend. CTOs can export the same rollup as CSV at
`/reports/executive/export`; the export writes `report.executive_exported` audit evidence with row
count and correlation ID metadata.

CTOs, platform administrators, and security auditors can review adoption rollups at
`/reports/adoption`. The report summarizes users with requests, projects with usage, active
assignments, department adoption, provider adoption, and project-level activity. CSV export is
available at `/reports/adoption/export` and writes `report.adoption_exported` audit evidence with
row count and correlation ID metadata.

## Extension Requests

Employees can request a later expiration date for active access at `/extensions`. CTOs and platform
administrators can approve or reject pending extensions; approvals update the request expiration and
provider assignment expiration while preserving audit and notification evidence.

## Local Demo Lifecycle

In local mode, the developer panel can simulate budget warning, critical, and enforcement thresholds.
Enforcement suspends the assignment, creates an incident, and notifies the requester and platform
administrators. Restore and forced expiration actions use the configured provider adapter, write
audit events, archive artifacts, deprovision access, notify participants, and close the request.
Use the local admin retention control, or `POST /developer/archives/enforce-retention`, to queue
an archive-retention lifecycle job that purges expired archive locations while preserving checksum
and audit evidence.
Live provider operations remain gated by `PROVIDER_LIVE_OPERATIONS_ENABLED`.

## Credential Rotation

Rotate external credentials through the secret manager, validate provider configuration, and record the rotation evidence.
