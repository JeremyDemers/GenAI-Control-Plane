import type { AccessRequestFormValues } from "@/lib/request-schema";

export type DevUser =
  | "employee@example.local"
  | "owner@example.local"
  | "approver@example.local"
  | "security@example.local"
  | "admin@example.local"
  | "auditor@example.local"
  | "cto@example.local";

export type AccessRequest = {
  id: string;
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

export type CurrentUser = {
  id: string;
  email: string;
  display_name: string;
  roles: string[];
};

export type PolicyEvaluation = {
  id: string;
  request_id: string;
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

export type LifecycleAction = {
  assignment_id: string;
  request_id: string;
  status: string;
  request_status: string;
  audit_event: string;
};

export type AuditEvent = {
  id: string;
  event_type: string;
  actor_user_id: string | null;
  target_type: string;
  target_id: string | null;
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

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, user: DevUser, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      "x-dev-user": user,
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return (await response.json()) as T;
}

export function getMe(user: DevUser) {
  return request<CurrentUser>("/auth/me", user);
}

export function listRequests(user: DevUser) {
  return request<AccessRequest[]>("/access-requests", user);
}

export function createAccessRequest(user: DevUser, payload: AccessRequestFormValues) {
  return request<AccessRequest>("/access-requests", user, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function cancelAccessRequest(user: DevUser, requestId: string) {
  return request<AccessRequest>(`/access-requests/${requestId}/cancel`, user, {
    method: "POST"
  });
}

export function getPolicyEvaluation(user: DevUser, requestId: string) {
  return request<PolicyEvaluation>(`/access-requests/${requestId}/policy-evaluation`, user);
}

export function listPendingApprovals(user: DevUser) {
  return request<PendingApproval[]>("/approvals/pending", user);
}

export function decideApproval(user: DevUser, stepId: string, decision: "approve" | "reject") {
  return request<AccessRequest>(`/approvals/${stepId}`, user, {
    method: "POST",
    body: JSON.stringify({ decision, comments: "Reviewed in local demo." })
  });
}

export function listAssignments(user: DevUser) {
  return request<ProviderAssignment[]>("/developer/assignments", user);
}

export function simulateUsage(
  user: DevUser,
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

export function restoreAssignment(user: DevUser, assignmentId: string) {
  return request<LifecycleAction>("/developer/restore", user, {
    method: "POST",
    body: JSON.stringify({ assignment_id: assignmentId, reason: "Administrator restored demo access." })
  });
}

export function expireAssignment(user: DevUser, assignmentId: string) {
  return request<LifecycleAction>("/developer/expire", user, {
    method: "POST",
    body: JSON.stringify({
      assignment_id: assignmentId,
      reason: "Developer panel forced expiration for demo."
    })
  });
}

export function listAuditEvents(user: DevUser) {
  return request<AuditEvent[]>("/audit-events", user);
}

export async function exportAuditEvents(user: DevUser) {
  const response = await fetch(`${apiBase}/audit-events/export`, {
    headers: {
      "x-dev-user": user
    }
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.text();
}

export function listArchives(user: DevUser) {
  return request<ArtifactArchive[]>("/developer/archives", user);
}

export function listNotifications(user: DevUser) {
  return request<Notification[]>("/notifications", user);
}

export function markNotificationRead(user: DevUser, notificationId: string) {
  return request<Notification>(`/notifications/${notificationId}/read`, user, {
    method: "POST"
  });
}

export function getExecutiveReport(user: DevUser) {
  return request<ExecutiveReport>("/reports/executive", user);
}

export function listIncidents(user: DevUser) {
  return request<Incident[]>("/incidents", user);
}

export function resolveIncident(user: DevUser, incidentId: string) {
  return request<Incident>(`/incidents/${incidentId}/resolve`, user, {
    method: "POST",
    body: JSON.stringify({ reason: "Reviewed and resolved in the local operations demo." })
  });
}

export function listExtensions(user: DevUser) {
  return request<ExtensionRequest[]>("/extensions", user);
}

export function createExtensionRequest(user: DevUser, requestId: string, currentEndAt: string) {
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

export function decideExtension(user: DevUser, extensionId: string, decision: "approve" | "reject") {
  return request<ExtensionRequest>(`/extensions/${extensionId}/decision`, user, {
    method: "POST",
    body: JSON.stringify({ decision, comments: "Reviewed in local demo." })
  });
}
