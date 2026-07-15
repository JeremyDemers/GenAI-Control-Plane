import type { AccessRequestFormValues } from "@/lib/request-schema";
import type { OidcSession } from "@/lib/auth";
import { apiBaseUrl, apiDocsUrl } from "@/lib/api-config";

export type DevUser =
  | "employee@example.local"
  | "owner@example.local"
  | "owner2@example.local"
  | "approver@example.local"
  | "security@example.local"
  | "admin@example.local"
  | "auditor@example.local"
  | "cto@example.local";

export type ApiIdentity = DevUser | OidcSession;

export type AccessRequest = {
  id: string;
  project_id: string | null;
  project_name: string;
  requester_id: string;
  status: string;
  business_justification: string;
  data_classification: string;
  requested_budget: string;
  currency: string;
  provider_names: string[];
  requested_start_at: string;
  requested_end_at: string;
  submitted_at: string | null;
  expires_at: string | null;
};

export type Project = {
  id: string;
  name: string;
  cost_center: string;
  owner_user_id: string | null;
  status: string;
  member_count: number;
  created_at: string;
};

export type ProjectMember = {
  id: string;
  project_id: string;
  user_id: string;
  email: string;
  display_name: string;
  member_role: string;
  created_at: string;
};

export type CurrentUser = {
  id: string;
  email: string;
  display_name: string;
  roles: string[];
};

export type PolicyEvaluation = {
  id: string;
  request_id: string;
  policy_version_id: string;
  triggered_rules: string[];
  approval_path: string[];
  restrictions: string[];
  final_decision: string;
  evaluated_at: string;
};

export type PendingApproval = {
  step_id: string;
  request_id: string;
  step_type: string;
  assigned_role: string;
};

export type ApprovalHistory = {
  approval_step_id: string;
  request_id: string;
  project_name: string;
  step_type: string;
  assigned_role: string;
  step_status: string;
  decision_id: string | null;
  decision: string | null;
  comments: string;
  actor_email: string | null;
  decided_at: string | null;
  step_created_at: string;
};

export type PolicyVersion = {
  id: string;
  policy_definition_id: string;
  name: string;
  description: string;
  version: number;
  document: Record<string, unknown>;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type RetentionPolicy = {
  policy_version_id: string;
  version: number;
  artifact_retention_days: number;
  active: boolean;
  updated_at: string;
};

export type ProviderHealth = {
  provider: string;
  status: string;
  latency_ms: number;
  details: Record<string, unknown>;
};

export type ProviderConfiguration = {
  provider: string;
  configured: boolean;
  mode: string;
  details: Record<string, unknown>;
};

export type IntegrationCredential = {
  id: string;
  provider: string;
  credential_reference: string;
  rotation_due_at: string | null;
  updated_at: string;
};

export type ProviderAssignment = {
  id: string;
  request_id: string;
  provider: string;
  status: string;
  external_resource_id: string;
  expires_at: string | null;
  total_cost: string;
  total_tokens: number;
  freshness_at: string | null;
};

export type UsageRecord = {
  id: string;
  assignment_id: string;
  provider: string;
  tokens: number;
  request_count: number;
  measured_at: string;
  freshness_at: string;
};

export type CostRecord = {
  id: string;
  assignment_id: string;
  provider: string;
  amount: string;
  currency: string;
  cost_type: string;
  freshness_at: string;
};

export type BudgetSummary = {
  request_id: string;
  project_name: string;
  requested_budget: string;
  total_spend: string;
  remaining_budget: string;
  utilization_percent: number;
  currency: string;
  freshness_at: string | null;
};

export type LifecycleAction = {
  assignment_id: string;
  request_id: string;
  status: string;
  request_status: string;
  audit_event: string;
};

export type LifecycleJob = {
  id: string;
  job_type: string;
  status: string;
  attempt_count: number;
  idempotency_key: string;
  payload: Record<string, unknown>;
  failure_information: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type OperationalHealth = {
  status: string;
  requests: {
    requests_total: number;
    status_counts: Record<string, number>;
    top_routes: Record<string, number>;
    average_duration_ms: number;
    max_duration_ms: number;
  };
  lifecycle_jobs: {
    status_counts: Record<string, number>;
    queued_or_failed: number;
  };
};

export type AuditEvent = {
  id: string;
  event_type: string;
  actor_user_id: string | null;
  target_type: string;
  target_id: string | null;
  request_id: string | null;
  project_id: string | null;
  provider: string | null;
  action: string;
  result: string;
  reason: string;
  correlation_id: string;
  created_at: string;
};

export type ArtifactArchive = {
  id: string;
  assignment_id: string | null;
  storage_provider: string;
  storage_location: string;
  checksum: string;
  retention_expires_at: string;
};

export type ProvisioningEvidence = {
  assignment_id: string;
  request_id: string;
  project_id: string | null;
  project_name: string;
  provider: string;
  assignment_status: string;
  external_resource_id: string;
  provision_job_status: string | null;
  archive_job_status: string | null;
  archive_location: string | null;
  archive_checksum: string | null;
  deprovisioned_at: string | null;
  evidence_result: string;
  updated_at: string;
};

export type Incident = {
  id: string;
  severity: string;
  status: string;
  summary: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Notification = {
  id: string;
  user_id: string;
  event_type: string;
  message: string;
  read_at: string | null;
  delivery_status: string;
  delivery_attempts: number;
  delivered_at: string | null;
  created_at: string;
};

export type ExecutiveReport = {
  total_requests: number;
  active_projects: number;
  pending_approvals: number;
  suspended_projects: number;
  total_budget: string;
  total_spend: string;
  remaining_budget: string;
  requests_by_status: Record<string, number>;
  spend_by_provider: {
    provider: string;
    spend: string;
    tokens: number;
    active_assignments: number;
  }[];
  spend_by_cost_center: {
    cost_center: string;
    budget: string;
    spend: string;
    remaining_budget: string;
  }[];
};

export type ExtensionRequest = {
  id: string;
  request_id: string;
  requester_id: string;
  requested_end_at: string;
  status: string;
  justification: string;
  created_at: string;
  updated_at: string;
};

export type ReassignmentRequest = {
  id: string;
  project_id: string;
  project_name: string;
  current_owner_id: string;
  current_owner_email: string;
  proposed_owner_id: string;
  proposed_owner_email: string;
  status: string;
  justification: string;
  created_at: string;
  updated_at: string;
};

export type RoleChange = {
  id: string;
  project_id: string | null;
  project_name: string | null;
  target_email: string;
  old_role: string;
  new_role: string;
  actor_email: string | null;
  source_event_type: string;
  reason: string;
  created_at: string;
};

export type CostAllocationDelivery = {
  id: string;
  status: string;
  frequency: string;
  recipients: string[];
  row_count: number;
  created_at: string;
};

export { apiDocsUrl };

function authHeaders(identity: ApiIdentity): Record<string, string> {
  if (typeof identity === "string") {
    return { "x-dev-user": identity };
  }
  return { Authorization: `Bearer ${identity.accessToken}` };
}

async function request<T>(path: string, identity: ApiIdentity, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...authHeaders(identity),
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return (await response.json()) as T;
}

export function getMe(user: ApiIdentity) {
  return request<CurrentUser>("/auth/me", user);
}

export function listRequests(user: ApiIdentity) {
  return request<AccessRequest[]>("/access-requests", user);
}

export function listProjects(user: ApiIdentity) {
  return request<Project[]>("/projects", user);
}

export function listProjectMembers(user: ApiIdentity, projectId: string) {
  return request<ProjectMember[]>(`/projects/${projectId}/members`, user);
}

export function listProjectAuditEvents(user: ApiIdentity, projectId: string) {
  return request<AuditEvent[]>(`/projects/${projectId}/audit-events`, user);
}

export function addProjectMember(
  user: ApiIdentity,
  projectId: string,
  email = "security@example.local",
  memberRole = "collaborator"
) {
  return request<ProjectMember>(`/projects/${projectId}/members`, user, {
    method: "POST",
    body: JSON.stringify({ email, member_role: memberRole })
  });
}

export function suspendProject(user: ApiIdentity, projectId: string) {
  return request<Project>(`/projects/${projectId}/suspend`, user, {
    method: "POST",
    body: JSON.stringify({ reason: "Executive risk review paused this project." })
  });
}

export function listReassignments(user: ApiIdentity) {
  return request<ReassignmentRequest[]>("/reassignments", user);
}

export function listRoleChanges(user: ApiIdentity) {
  return request<RoleChange[]>("/role-changes", user);
}

export function createReassignment(user: ApiIdentity, projectId: string) {
  return request<ReassignmentRequest>("/reassignments", user, {
    method: "POST",
    body: JSON.stringify({
      project_id: projectId,
      proposed_owner_email: "owner2@example.local",
      justification: "Move ownership to the backup project owner for continuity."
    })
  });
}

export function acceptReassignment(user: ApiIdentity, reassignmentId: string) {
  return request<ReassignmentRequest>(`/reassignments/${reassignmentId}/accept`, user, {
    method: "POST"
  });
}

export function decideReassignment(
  user: ApiIdentity,
  reassignmentId: string,
  decision: "approve" | "reject"
) {
  return request<ReassignmentRequest>(`/reassignments/${reassignmentId}/decision`, user, {
    method: "POST",
    body: JSON.stringify({
      decision,
      comments: "Reviewed in local demo."
    })
  });
}

export function createAccessRequest(user: ApiIdentity, payload: AccessRequestFormValues) {
  return request<AccessRequest>("/access-requests", user, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function cancelAccessRequest(user: ApiIdentity, requestId: string) {
  return request<AccessRequest>(`/access-requests/${requestId}/cancel`, user, {
    method: "POST"
  });
}

export function getPolicyEvaluation(user: ApiIdentity, requestId: string) {
  return request<PolicyEvaluation>(`/access-requests/${requestId}/policy-evaluation`, user);
}

export function listPolicies(user: ApiIdentity) {
  return request<PolicyVersion[]>("/policies", user);
}

export function getRetentionPolicy(user: ApiIdentity) {
  return request<RetentionPolicy>("/policies/retention", user);
}

export function updateRetentionPolicy(user: ApiIdentity) {
  return request<RetentionPolicy>("/policies/retention", user, {
    method: "POST",
    body: JSON.stringify({
      artifact_retention_days: 30,
      reason: "Reduce demo artifact retention for regulated cleanup evidence."
    })
  });
}

export function publishInternalSecurityReviewPolicy(user: ApiIdentity, activePolicy: PolicyVersion) {
  const document = JSON.parse(JSON.stringify(activePolicy.document)) as {
    approval_rules?: { require_security_review_for?: string[] };
  } & Record<string, unknown>;
  document.approval_rules = {
    ...(document.approval_rules ?? {}),
    require_security_review_for: ["internal", "confidential", "regulated"]
  };
  return request<PolicyVersion>("/policies/standard-ai-sandbox/versions", user, {
    method: "POST",
    body: JSON.stringify({
      document,
      description: "Default governed sandbox policy with internal security review."
    })
  });
}

export function listPendingApprovals(user: ApiIdentity) {
  return request<PendingApproval[]>("/approvals/pending", user);
}

export function listApprovalHistory(user: ApiIdentity) {
  return request<ApprovalHistory[]>("/approvals/history", user);
}

export function listProviderHealth(user: ApiIdentity) {
  return request<ProviderHealth[]>("/providers/health", user);
}

export function listProviderConfiguration(user: ApiIdentity) {
  return request<ProviderConfiguration[]>("/providers/configuration", user);
}

export function listIntegrationCredentials(user: ApiIdentity) {
  return request<IntegrationCredential[]>("/providers/credentials", user);
}

export function rotateIntegrationCredential(user: ApiIdentity, credentialId: string) {
  return request<IntegrationCredential>(`/providers/credentials/${credentialId}/rotate`, user, {
    method: "POST",
    body: JSON.stringify({
      reason: "Rotate demo provider credential reference for governance evidence."
    })
  });
}

export function decideApproval(
  user: ApiIdentity,
  stepId: string,
  decision: "approve" | "reject" | "request_information"
) {
  return request<AccessRequest>(`/approvals/${stepId}`, user, {
    method: "POST",
    body: JSON.stringify({
      decision,
      comments:
        decision === "request_information"
          ? "Please clarify retention and artifact handling before approval."
          : "Reviewed in local demo."
    })
  });
}

export function overrideApproval(user: ApiIdentity, requestId: string, decision: "approve" | "reject") {
  return request<AccessRequest>(`/approvals/override/${requestId}`, user, {
    method: "POST",
    body: JSON.stringify({
      decision,
      justification: "Urgent executive demo requires direct temporary approval."
    })
  });
}

export function respondToInformationRequest(user: ApiIdentity, requestId: string) {
  return request<AccessRequest>(`/access-requests/${requestId}/information-response`, user, {
    method: "POST",
    body: JSON.stringify({
      response:
        "Artifacts will be retained for seven days, archived with checksum evidence, and removed during closure."
    })
  });
}

export function listAssignments(user: ApiIdentity) {
  return request<ProviderAssignment[]>("/developer/assignments", user);
}

export function listProviderAssignments(user: ApiIdentity) {
  return request<ProviderAssignment[]>("/provider-assignments", user);
}

export function listUsageRecords(user: ApiIdentity) {
  return request<UsageRecord[]>("/usage", user);
}

export function listCostRecords(user: ApiIdentity) {
  return request<CostRecord[]>("/costs", user);
}

export function listBudgetSummaries(user: ApiIdentity) {
  return request<BudgetSummary[]>("/budgets", user);
}

export function simulateUsage(
  user: ApiIdentity,
  assignmentId: string,
  preset: "warning" | "critical" | "enforcement"
) {
  const payloadByPreset = {
    warning: { tokens: 70000, request_count: 140, cost_amount: "70" },
    critical: { tokens: 20000, request_count: 40, cost_amount: "20" },
    enforcement: { tokens: 10000, request_count: 20, cost_amount: "10" }
  };
  return request<LifecycleAction>("/developer/simulate-usage", user, {
    method: "POST",
    body: JSON.stringify({ assignment_id: assignmentId, ...payloadByPreset[preset] })
  });
}

export function restoreAssignment(user: ApiIdentity, assignmentId: string) {
  return request<LifecycleAction>("/developer/restore", user, {
    method: "POST",
    body: JSON.stringify({ assignment_id: assignmentId, reason: "Administrator restored demo access." })
  });
}

export function expireAssignment(user: ApiIdentity, assignmentId: string) {
  return request<LifecycleAction>("/developer/expire", user, {
    method: "POST",
    body: JSON.stringify({
      assignment_id: assignmentId,
      reason: "Developer panel forced expiration for demo."
    })
  });
}

export function listLifecycleJobs(user: ApiIdentity) {
  return request<LifecycleJob[]>("/lifecycle-jobs", user);
}

export function getOperationalHealth(user: ApiIdentity) {
  return request<OperationalHealth>("/health/observability", user);
}

export function retryLifecycleJob(user: ApiIdentity, jobId: string) {
  return request<LifecycleJob>(`/lifecycle-jobs/${jobId}/retry`, user, {
    method: "POST"
  });
}

export function listAuditEvents(user: ApiIdentity) {
  return request<AuditEvent[]>("/audit-events", user);
}

export async function exportAuditEvents(user: ApiIdentity) {
  const response = await fetch(`${apiBaseUrl()}/audit-events/export`, {
    headers: authHeaders(user)
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.text();
}

export async function exportCostAllocation(user: ApiIdentity) {
  const response = await fetch(`${apiBaseUrl()}/reports/cost-allocation/export`, {
    headers: authHeaders(user)
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.text();
}

export function listArchives(user: ApiIdentity) {
  return request<ArtifactArchive[]>("/developer/archives", user);
}

export function enforceArchiveRetention(user: ApiIdentity) {
  return request<LifecycleJob>("/developer/archives/enforce-retention", user, {
    method: "POST"
  });
}

export function listProvisioningEvidence(user: ApiIdentity) {
  return request<ProvisioningEvidence[]>("/evidence/provisioning", user);
}

export function listNotifications(user: ApiIdentity) {
  return request<Notification[]>("/notifications", user);
}

export function markNotificationRead(user: ApiIdentity, notificationId: string) {
  return request<Notification>(`/notifications/${notificationId}/read`, user, {
    method: "POST"
  });
}

export function getExecutiveReport(user: ApiIdentity) {
  return request<ExecutiveReport>("/reports/executive", user);
}

export function listCostAllocationDeliveries(user: ApiIdentity) {
  return request<CostAllocationDelivery[]>("/reports/cost-allocation/deliveries", user);
}

export function scheduleCostAllocationDelivery(user: ApiIdentity) {
  return request<CostAllocationDelivery>("/reports/cost-allocation/deliveries", user, {
    method: "POST",
    body: JSON.stringify({ frequency: "weekly", recipients: ["finance@example.local"] })
  });
}

export function listIncidents(user: ApiIdentity) {
  return request<Incident[]>("/incidents", user);
}

export function resolveIncident(user: ApiIdentity, incidentId: string) {
  return request<Incident>(`/incidents/${incidentId}/resolve`, user, {
    method: "POST",
    body: JSON.stringify({ reason: "Reviewed and resolved in the local operations demo." })
  });
}

export function listExtensions(user: ApiIdentity) {
  return request<ExtensionRequest[]>("/extensions", user);
}

export function createExtensionRequest(user: ApiIdentity, requestId: string, currentEndAt: string) {
  const requestedEndAt = new Date(currentEndAt);
  requestedEndAt.setDate(requestedEndAt.getDate() + 7);
  return request<ExtensionRequest>("/extensions", user, {
    method: "POST",
    body: JSON.stringify({
      request_id: requestId,
      requested_end_at: requestedEndAt.toISOString(),
      justification: "Need one more week to complete stakeholder validation and archive evidence."
    })
  });
}

export function decideExtension(user: ApiIdentity, extensionId: string, decision: "approve" | "reject") {
  return request<ExtensionRequest>(`/extensions/${extensionId}/decision`, user, {
    method: "POST",
    body: JSON.stringify({ decision, comments: "Reviewed in local demo." })
  });
}
