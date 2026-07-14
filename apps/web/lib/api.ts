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

