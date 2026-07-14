"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Archive,
  Bell,
  CheckCircle2,
  Clock3,
  CloudCog,
  FileClock,
  LineChart,
  RotateCcw,
  ShieldCheck,
  UserRound,
  Zap
} from "lucide-react";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import {
  cancelAccessRequest,
  createAccessRequest,
  createExtensionRequest,
  decideExtension,
  decideApproval,
  expireAssignment,
  exportAuditEvents,
  getExecutiveReport,
  getMe,
  getPolicyEvaluation,
  listArchives,
  listAssignments,
  listAuditEvents,
  listBudgetSummaries,
  listCostRecords,
  listExtensions,
  listIncidents,
  listNotifications,
  listPolicies,
  listPendingApprovals,
  listProviderConfiguration,
  listProviderAssignments,
  listProviderHealth,
  listProjectMembers,
  listProjects,
  listRequests,
  listUsageRecords,
  markNotificationRead,
  publishInternalSecurityReviewPolicy,
  restoreAssignment,
  resolveIncident,
  simulateUsage,
  type AccessRequest,
  type DevUser
} from "@/lib/api";
import {
  accessRequestSchema,
  providerOptions,
  type AccessRequestFormValues
} from "@/lib/request-schema";

const users: DevUser[] = [
  "employee@example.local",
  "owner@example.local",
  "approver@example.local",
  "cto@example.local",
  "admin@example.local",
  "auditor@example.local"
];

const costTrend = [
  { day: "Mon", cost: 12 },
  { day: "Tue", cost: 28 },
  { day: "Wed", cost: 46 },
  { day: "Thu", cost: 71 },
  { day: "Fri", cost: 92 },
  { day: "Sat", cost: 100 }
];

const providerSpend = [
  { provider: "AWS", spend: 44 },
  { provider: "GitHub", spend: 28 },
  { provider: "Azure", spend: 14 },
  { provider: "Google", spend: 9 }
];

function nextIso(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  date.setMilliseconds(0);
  return date.toISOString();
}

const defaultValues: AccessRequestFormValues = {
  project_name: "Interview Demo Sandbox",
  business_justification: "Evaluate governed AI assistance for customer support workflows.",
  project_sponsor: "Casey CTO",
  cost_center: "ENG-AI",
  requested_start_at: nextIso(1),
  requested_end_at: nextIso(15),
  requested_budget: 100,
  currency: "USD",
  requested_providers: ["amazon_bedrock", "github_copilot"],
  requested_services: ["claude-sonnet", "copilot-business"],
  expected_users: 4,
  requested_collaborators: ["owner@example.local"],
  data_classification: "internal",
  uses_pii: false,
  uses_confidential_data: false,
  uses_regulated_data: false,
  uses_source_code: true,
  expected_artifacts: ["prompt templates", "usage report"],
  expected_usage_pattern: "Burst testing during a two-week prototype.",
  estimated_monthly_volume: 200000,
  additional_notes: "Seeded for the portfolio demo."
};

export function ControlCenter() {
  const [user, setUser] = useState<DevUser>("employee@example.local");
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["me", user], queryFn: () => getMe(user) });
  const requests = useQuery({ queryKey: ["requests", user], queryFn: () => listRequests(user) });
  const projects = useQuery({ queryKey: ["projects", user], queryFn: () => listProjects(user) });
  const approvals = useQuery({
    queryKey: ["approvals", user],
    queryFn: () => listPendingApprovals(user),
    retry: false
  });
  const providerHealth = useQuery({
    queryKey: ["provider-health", user],
    queryFn: () => listProviderHealth(user),
    retry: false
  });
  const providerConfiguration = useQuery({
    queryKey: ["provider-configuration", user],
    queryFn: () => listProviderConfiguration(user),
    enabled: user === "admin@example.local" || user === "auditor@example.local" || user === "cto@example.local",
    retry: false
  });
  const assignments = useQuery({
    queryKey: ["assignments", user],
    queryFn: () => listAssignments(user),
    enabled: user === "admin@example.local",
    retry: false
  });
  const providerAssignments = useQuery({
    queryKey: ["provider-assignments", user],
    queryFn: () => listProviderAssignments(user),
    retry: false
  });
  const usageRecords = useQuery({
    queryKey: ["usage-records", user],
    queryFn: () => listUsageRecords(user),
    retry: false
  });
  const costRecords = useQuery({
    queryKey: ["cost-records", user],
    queryFn: () => listCostRecords(user),
    retry: false
  });
  const budgetSummaries = useQuery({
    queryKey: ["budget-summaries", user],
    queryFn: () => listBudgetSummaries(user),
    retry: false
  });
  const archives = useQuery({
    queryKey: ["archives", user],
    queryFn: () => listArchives(user),
    enabled: user === "admin@example.local",
    retry: false
  });
  const auditEvents = useQuery({
    queryKey: ["audit-events", user],
    queryFn: () => listAuditEvents(user),
    enabled: user === "auditor@example.local",
    retry: false
  });
  const notifications = useQuery({
    queryKey: ["notifications", user],
    queryFn: () => listNotifications(user),
    retry: false
  });
  const executiveReport = useQuery({
    queryKey: ["executive-report", user],
    queryFn: () => getExecutiveReport(user),
    enabled: user === "cto@example.local",
    retry: false
  });
  const incidents = useQuery({
    queryKey: ["incidents", user],
    queryFn: () => listIncidents(user),
    enabled: user === "admin@example.local" || user === "auditor@example.local" || user === "cto@example.local",
    retry: false
  });
  const policies = useQuery({
    queryKey: ["policies", user],
    queryFn: () => listPolicies(user),
    enabled: user === "admin@example.local" || user === "auditor@example.local",
    retry: false
  });
  const extensions = useQuery({
    queryKey: ["extensions", user],
    queryFn: () => listExtensions(user),
    retry: false
  });
  const selectedRequest = useMemo(
    () => requests.data?.find((request) => request.id === selectedRequestId) ?? requests.data?.[0],
    [requests.data, selectedRequestId]
  );
  const selectedRequestProjectId = selectedRequest?.project_id;
  const selectedProjectId = projects.data?.some((project) => project.id === selectedRequestProjectId)
    ? selectedRequestProjectId
    : projects.data?.[0]?.id;
  const projectMembers = useQuery({
    queryKey: ["project-members", user, selectedProjectId],
    queryFn: () => listProjectMembers(user, selectedProjectId ?? ""),
    enabled: Boolean(selectedProjectId),
    retry: false
  });
  const evaluation = useQuery({
    queryKey: ["policy-evaluation", user, selectedRequest?.id],
    queryFn: () => getPolicyEvaluation(user, selectedRequest?.id ?? ""),
    enabled: Boolean(selectedRequest?.id)
  });

  const form = useForm<AccessRequestFormValues>({
    resolver: zodResolver(accessRequestSchema),
    defaultValues,
    shouldUnregister: false
  });

  const createMutation = useMutation({
    mutationFn: (values: AccessRequestFormValues) => createAccessRequest(user, values),
    onSuccess: (created) => {
      setSelectedRequestId(created.id);
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["project-members"] });
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
      void queryClient.invalidateQueries({ queryKey: ["assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["budget-summaries"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  });

  const approvalMutation = useMutation({
    mutationFn: ({ stepId, decision }: { stepId: string; decision: "approve" | "reject" }) =>
      decideApproval(user, stepId, decision),
    onSuccess: (updated) => {
      setSelectedRequestId(updated.id);
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
      void queryClient.invalidateQueries({ queryKey: ["policy-evaluation"] });
      void queryClient.invalidateQueries({ queryKey: ["assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["budget-summaries"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  });
  const cancelMutation = useMutation({
    mutationFn: (requestId: string) => cancelAccessRequest(user, requestId),
    onSuccess: (updated) => {
      setSelectedRequestId(updated.id);
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["budget-summaries"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  });

  const lifecycleMutation = useMutation({
    mutationFn: ({
      assignmentId,
      action
    }: {
      assignmentId: string;
      action: "warning" | "critical" | "enforcement" | "restore" | "expire";
    }) => {
      if (action === "restore") {
        return restoreAssignment(user, assignmentId);
      }
      if (action === "expire") {
        return expireAssignment(user, assignmentId);
      }
      return simulateUsage(user, assignmentId, action);
    },
    onSuccess: (result) => {
      setSelectedRequestId(result.request_id);
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["usage-records"] });
      void queryClient.invalidateQueries({ queryKey: ["cost-records"] });
      void queryClient.invalidateQueries({ queryKey: ["budget-summaries"] });
      void queryClient.invalidateQueries({ queryKey: ["archives"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["incidents"] });
    }
  });
  const readNotificationMutation = useMutation({
    mutationFn: (notificationId: string) => markNotificationRead(user, notificationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  });
  const auditExportMutation = useMutation({
    mutationFn: () => exportAuditEvents(user)
  });
  const extensionMutation = useMutation({
    mutationFn: ({ requestId, currentEndAt }: { requestId: string; currentEndAt: string }) =>
      createExtensionRequest(user, requestId, currentEndAt),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["extensions"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  });
  const extensionDecisionMutation = useMutation({
    mutationFn: ({ extensionId, decision }: { extensionId: string; decision: "approve" | "reject" }) =>
      decideExtension(user, extensionId, decision),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["extensions"] });
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["budget-summaries"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  });
  const incidentResolveMutation = useMutation({
    mutationFn: (incidentId: string) => resolveIncident(user, incidentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["incidents"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
    }
  });
  const policyPublishMutation = useMutation({
    mutationFn: () => {
      const activePolicy = policies.data?.find((policy) => policy.active);
      if (!activePolicy) {
        throw new Error("No active policy version found.");
      }
      return publishInternalSecurityReviewPolicy(user, activePolicy);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["policies"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
    }
  });

  const activeRequests = requests.data?.filter((request) => request.status === "ACTIVE").length ?? 0;
  const pendingRequests =
    requests.data?.filter((request) => request.status.includes("AWAITING")).length ?? 0;
  const unreadNotifications =
    notifications.data?.filter((notification) => !notification.read_at).length ?? 0;
  const latestUsage = usageRecords.data?.[0];
  const latestCost = costRecords.data?.[0];
  const visibleAssignments = providerAssignments.data?.length ?? 0;
  const healthyProviders =
    providerHealth.data?.filter((provider) => provider.status === "healthy").length ?? 0;
  const totalProviders = providerHealth.data?.length ?? 0;
  const allProvidersHealthy = totalProviders > 0 && healthyProviders === totalProviders;

  return (
    <main className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-normal text-ink">
              AI Access Control Center
            </h1>
            <p className="text-sm text-slate-600">
              {me.data?.display_name ?? "Development user"} · {me.data?.roles.join(", ") ?? "loading"}
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <UserRound className="h-4 w-4" aria-hidden />
            <select
              data-testid="identity-switcher"
              className="h-10 rounded-md border border-line bg-white px-3 shadow-quiet"
              value={user}
              onChange={(event) => setUser(event.target.value as DevUser)}
            >
              {users.map((identity) => (
                <option key={identity} value={identity}>
                  {identity}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      <section className="border-b border-line bg-panel">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-3 px-5 py-5 lg:grid-cols-4">
          <Metric icon={Clock3} label="Pending approvals" value={pendingRequests.toString()} />
          <Metric icon={CheckCircle2} label="Active projects" value={activeRequests.toString()} />
          <Metric icon={Bell} label="Unread alerts" value={unreadNotifications.toString()} tone="amber" />
          <Metric
            icon={CloudCog}
            label="Provider health"
            value={`${healthyProviders}/${totalProviders || 7}`}
            tone={allProvidersHealthy ? "mint" : "amber"}
          />
        </div>
      </section>

      <div className="mx-auto grid max-w-7xl gap-5 px-5 py-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="grid gap-5">
          <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="Spend Trend" icon={Activity}>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={costTrend}>
                    <CartesianGrid stroke="#d8dee8" strokeDasharray="3 3" />
                    <XAxis dataKey="day" />
                    <YAxis />
                    <Tooltip />
                    <Area dataKey="cost" stroke="#1f8f75" fill="#cfeee6" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Panel>
            <Panel title="Provider Spend" icon={ShieldCheck}>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={providerSpend}>
                    <CartesianGrid stroke="#d8dee8" strokeDasharray="3 3" />
                    <XAxis dataKey="provider" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="spend" fill="#4267ac" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </div>

          <Panel title="Provider Health" icon={CloudCog}>
            <div className="grid gap-3 md:grid-cols-2">
              {(providerHealth.data ?? []).map((provider) => (
                <div key={provider.provider} className="rounded-md border border-line p-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold">{provider.provider.replaceAll("_", " ")}</p>
                    <StatusPill status={provider.status} />
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    {provider.latency_ms}ms · {String(provider.details.mode ?? "unknown")}
                  </p>
                </div>
              ))}
              {providerHealth.data?.length === 0 ? (
                <p className="text-sm text-slate-500">Provider checks unavailable.</p>
              ) : null}
            </div>
            {providerConfiguration.data ? (
              <div className="mt-4 grid gap-2 border-t border-line pt-4">
                {providerConfiguration.data.map((provider) => (
                  <div
                    key={provider.provider}
                    className="flex items-center justify-between gap-3 text-sm"
                  >
                    <span>{provider.provider.replaceAll("_", " ")}</span>
                    <span className="font-semibold">
                      {provider.configured ? "configured" : "missing"} · {provider.mode}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
          </Panel>

          <Panel title="Projects" icon={UserRound}>
            <div className="grid gap-3">
              {(projects.data ?? []).slice(0, 4).map((project) => (
                <div key={project.id} className="rounded-md border border-line p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold">{project.name}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {project.cost_center} · {project.member_count} members
                      </p>
                    </div>
                    <StatusPill status={project.status} />
                  </div>
                </div>
              ))}
              {projectMembers.data && projectMembers.data.length > 0 ? (
                <div className="rounded-md border border-line bg-panel p-3 text-sm">
                  <p className="font-semibold">Project members</p>
                  <div className="mt-2 grid gap-2">
                    {projectMembers.data.map((member) => (
                      <div key={member.id} className="flex items-center justify-between gap-3">
                        <span>{member.email}</span>
                        <span className="text-xs font-semibold text-slate-500">
                          {member.member_role}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {projects.data?.length === 0 ? (
                <p className="text-sm text-slate-500">No projects visible for this identity.</p>
              ) : null}
            </div>
          </Panel>

          <Panel title="Requests" icon={FileClock}>
            {extensionMutation.isSuccess ? (
              <p className="mb-3 rounded-md bg-panel p-2 text-sm text-slate-600">
                Extension requested.
              </p>
            ) : null}
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-slate-500">
                    <th className="py-2 pr-3 font-medium">Project</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                    <th className="py-2 pr-3 font-medium">Providers</th>
                    <th className="py-2 pr-3 font-medium">Budget</th>
                    <th className="py-2 pr-3 font-medium">Expires</th>
                    <th className="py-2 pr-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(requests.data ?? []).map((request) => (
                    <tr
                      key={request.id}
                      className="cursor-pointer border-b border-line/70 hover:bg-panel"
                      onClick={() => setSelectedRequestId(request.id)}
                    >
                      <td className="py-3 pr-3 font-medium">{request.project_name}</td>
                      <td className="py-3 pr-3">
                        <StatusPill status={request.status} />
                      </td>
                      <td className="py-3 pr-3 text-slate-600">
                        {request.provider_names.join(", ")}
                      </td>
                      <td className="py-3 pr-3">
                        {request.currency} {request.requested_budget}
                      </td>
                      <td className="py-3 pr-3 text-slate-600">
                        {new Date(request.requested_end_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 pr-3">
                        {user === "employee@example.local" && request.status.includes("AWAITING") ? (
                          <button
                            className="rounded-md border border-coral px-2 py-1 text-xs font-semibold text-coral"
                            onClick={(event) => {
                              event.stopPropagation();
                              cancelMutation.mutate(request.id);
                            }}
                          >
                            Cancel
                          </button>
                        ) : null}
                        {user === "employee@example.local" && request.status === "ACTIVE" ? (
                          <button
                            className="rounded-md border border-line px-2 py-1 text-xs font-semibold"
                            onClick={(event) => {
                              event.stopPropagation();
                              extensionMutation.mutate({
                                requestId: request.id,
                                currentEndAt: request.requested_end_at
                              });
                            }}
                          >
                            Extend
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                  {requests.data?.length === 0 ? (
                    <tr>
                      <td className="py-8 text-slate-500" colSpan={6}>
                        No requests for this identity.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Policy Evaluation" icon={ShieldCheck}>
            {evaluation.data ? (
              <div className="grid gap-3 text-sm md:grid-cols-3">
                <Detail label="Decision" value={evaluation.data.final_decision} />
                <Detail label="Approval path" value={evaluation.data.approval_path.join(" → ")} />
                <Detail label="Rules" value={evaluation.data.triggered_rules.join(", ")} />
              </div>
            ) : (
              <p className="text-sm text-slate-500">Select a request with a policy evaluation.</p>
            )}
          </Panel>

          <Panel title="Usage & Budget" icon={Activity}>
            <div className="grid gap-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Detail label="Visible assignments" value={visibleAssignments.toString()} />
                <Detail
                  label="Latest tokens"
                  value={latestUsage ? latestUsage.tokens.toLocaleString() : "0"}
                />
                <Detail
                  label="Latest cost"
                  value={latestCost ? `${latestCost.currency} ${latestCost.amount}` : "USD 0"}
                />
                <Detail
                  label="Cost type"
                  value={latestCost ? latestCost.cost_type.replaceAll("_", " ") : "pending"}
                />
              </div>
              <div className="grid gap-2">
                {(budgetSummaries.data ?? []).slice(0, 4).map((summary) => (
                  <div key={summary.request_id} className="rounded-md border border-line p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">{summary.project_name}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {summary.freshness_at
                            ? `Fresh ${new Date(summary.freshness_at).toLocaleTimeString()}`
                            : "No usage reported yet"}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold">
                          {summary.currency} {summary.total_spend} / {summary.requested_budget}
                        </p>
                        <p className="text-xs text-slate-500">
                          {summary.utilization_percent}% used · {summary.currency}{" "}
                          {summary.remaining_budget} remaining
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
                {budgetSummaries.data?.length === 0 ? (
                  <p className="text-sm text-slate-500">Budget evidence will appear after a request is submitted.</p>
                ) : null}
                {budgetSummaries.isError || usageRecords.isError || costRecords.isError ? (
                  <p className="text-sm text-coral">Usage and budget evidence unavailable.</p>
                ) : null}
              </div>
            </div>
          </Panel>

          {user === "admin@example.local" ? (
            <Panel title="Developer Controls" icon={Zap}>
              <div className="grid gap-3">
                {(assignments.data ?? []).map((assignment) => (
                  <div key={assignment.id} className="rounded-md border border-line p-3">
                    <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold">{assignment.provider.replaceAll("_", " ")}</p>
                          <StatusPill status={assignment.status} />
                        </div>
                        <p className="mt-1 break-all text-xs text-slate-500">
                          {assignment.external_resource_id}
                        </p>
                        <p className="mt-2 text-sm text-slate-600">
                          ${assignment.total_cost} · {assignment.total_tokens.toLocaleString()} tokens
                        </p>
                      </div>
                      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5 md:grid-cols-1">
                        <ActionButton
                          icon={AlertTriangle}
                          label="70%"
                          testId={`usage-warning-${assignment.provider}`}
                          onClick={() =>
                            lifecycleMutation.mutate({
                              assignmentId: assignment.id,
                              action: "warning"
                            })
                          }
                        />
                        <ActionButton
                          icon={AlertTriangle}
                          label="90%"
                          testId={`usage-critical-${assignment.provider}`}
                          onClick={() =>
                            lifecycleMutation.mutate({
                              assignmentId: assignment.id,
                              action: "critical"
                            })
                          }
                        />
                        <ActionButton
                          icon={ShieldCheck}
                          label="100%"
                          testId={`usage-enforcement-${assignment.provider}`}
                          onClick={() =>
                            lifecycleMutation.mutate({
                              assignmentId: assignment.id,
                              action: "enforcement"
                            })
                          }
                        />
                        <ActionButton
                          icon={RotateCcw}
                          label="Restore"
                          testId={`restore-${assignment.provider}`}
                          onClick={() =>
                            lifecycleMutation.mutate({
                              assignmentId: assignment.id,
                              action: "restore"
                            })
                          }
                        />
                        <ActionButton
                          icon={Archive}
                          label="Expire"
                          testId={`expire-${assignment.provider}`}
                          onClick={() =>
                            lifecycleMutation.mutate({
                              assignmentId: assignment.id,
                              action: "expire"
                            })
                          }
                        />
                      </div>
                    </div>
                  </div>
                ))}
                {assignments.data?.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    Approve a request through the manager and CTO steps to create assignments.
                  </p>
                ) : null}
                {archives.data && archives.data.length > 0 ? (
                  <div className="rounded-md border border-line bg-panel p-3 text-sm">
                    <p className="font-semibold">Latest archive</p>
                    <p className="mt-1 break-all text-slate-600">{archives.data[0].storage_location}</p>
                  </div>
                ) : null}
              </div>
            </Panel>
          ) : null}

          {user === "admin@example.local" || user === "auditor@example.local" ? (
            <Panel title="Policies" icon={ShieldCheck}>
              <div className="grid gap-3 text-sm">
                {policies.data?.find((policy) => policy.active) ? (
                  <div className="rounded-md border border-line p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">
                          {policies.data.find((policy) => policy.active)?.name}
                        </p>
                        <p className="mt-1 text-slate-600">
                          Version {policies.data.find((policy) => policy.active)?.version} · active
                        </p>
                      </div>
                      {user === "admin@example.local" ? (
                        <button
                          className="rounded-md border border-line px-3 py-2 text-xs font-semibold"
                          onClick={() => policyPublishMutation.mutate()}
                        >
                          Publish Review Policy
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">Policy versions unavailable.</p>
                )}
                {policyPublishMutation.data ? (
                  <p className="rounded-md bg-panel p-2 text-xs text-slate-600">
                    Published policy version {policyPublishMutation.data.version}.
                  </p>
                ) : null}
              </div>
            </Panel>
          ) : null}

          {user === "admin@example.local" || user === "auditor@example.local" ? (
            <Panel title="Incidents" icon={AlertTriangle}>
              <div className="grid gap-2">
                {(incidents.data ?? []).slice(0, 5).map((incident) => (
                  <div key={incident.id} className="rounded-md border border-line p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold">{incident.summary}</p>
                          <StatusPill status={incident.status} />
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          {incident.severity} · {new Date(incident.created_at).toLocaleTimeString()}
                        </p>
                      </div>
                      {user === "admin@example.local" && incident.status !== "resolved" ? (
                        <button
                          data-testid="resolve-incident"
                          className="rounded-md border border-line px-3 py-2 text-xs font-semibold"
                          onClick={() => incidentResolveMutation.mutate(incident.id)}
                        >
                          Resolve
                        </button>
                      ) : null}
                    </div>
                  </div>
                ))}
                {incidents.data?.length === 0 ? (
                  <p className="text-sm text-slate-500">No incidents.</p>
                ) : null}
              </div>
            </Panel>
          ) : null}

          {user === "auditor@example.local" ? (
            <Panel title="Audit Trail" icon={Archive}>
              <div className="grid gap-2">
                <button
                  className="h-10 rounded-md border border-line px-3 text-sm font-semibold"
                  onClick={() => auditExportMutation.mutate()}
                >
                  Export CSV
                </button>
                {auditExportMutation.data ? (
                  <p className="rounded-md bg-panel p-2 text-xs text-slate-600">
                    CSV export ready · {auditExportMutation.data.trim().split("\n").length - 1} rows
                  </p>
                ) : null}
                {(auditEvents.data ?? []).slice(0, 8).map((event) => (
                  <div key={event.id} className="rounded-md border border-line p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold">{event.event_type}</p>
                      <span className="text-xs text-slate-500">
                        {new Date(event.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="mt-1 text-slate-600">
                      {event.action} · {event.result}
                    </p>
                  </div>
                ))}
                {auditEvents.data?.length === 0 ? (
                  <p className="text-sm text-slate-500">No audit events yet.</p>
                ) : null}
              </div>
            </Panel>
          ) : null}

          {user === "cto@example.local" ? (
            <Panel title="Executive Report" icon={LineChart}>
              {executiveReport.data ? (
                <div className="grid gap-4">
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Detail label="Total spend" value={`$${executiveReport.data.total_spend}`} />
                    <Detail
                      label="Remaining budget"
                      value={`$${executiveReport.data.remaining_budget}`}
                    />
                    <Detail
                      label="Active projects"
                      value={executiveReport.data.active_projects.toString()}
                    />
                    <Detail
                      label="Pending approvals"
                      value={executiveReport.data.pending_approvals.toString()}
                    />
                  </div>
                  <div className="grid gap-3 lg:grid-cols-2">
                    <div className="rounded-md border border-line p-3">
                      <p className="text-sm font-semibold">Provider spend</p>
                      <div className="mt-2 grid gap-2">
                        {executiveReport.data.spend_by_provider.map((provider) => (
                          <div
                            key={provider.provider}
                            className="flex items-center justify-between gap-3 text-sm"
                          >
                            <span>{provider.provider.replaceAll("_", " ")}</span>
                            <span className="font-semibold">
                              ${provider.spend} · {provider.tokens.toLocaleString()} tokens
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-md border border-line p-3">
                      <p className="text-sm font-semibold">Cost centers</p>
                      <div className="mt-2 grid gap-2">
                        {executiveReport.data.spend_by_cost_center.map((center) => (
                          <div
                            key={center.cost_center}
                            className="flex items-center justify-between gap-3 text-sm"
                          >
                            <span>{center.cost_center}</span>
                            <span className="font-semibold">
                              ${center.spend} / ${center.budget}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-500">Executive report will populate after activity.</p>
              )}
            </Panel>
          ) : null}

          {user === "cto@example.local" || user === "admin@example.local" ? (
            <Panel title="Extension Queue" icon={Clock3}>
              <div className="grid gap-2">
                {(extensions.data ?? []).map((extension) => (
                  <div key={extension.id} className="rounded-md border border-line p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">{extension.status}</p>
                        <p className="break-all text-xs text-slate-500">{extension.request_id}</p>
                      </div>
                      {extension.status === "pending" ? (
                        <div className="flex gap-2">
                          <button
                            data-testid="approve-extension"
                            className="rounded-md bg-mint px-3 py-2 text-xs font-semibold text-white"
                            onClick={() =>
                              extensionDecisionMutation.mutate({
                                extensionId: extension.id,
                                decision: "approve"
                              })
                            }
                          >
                            Approve
                          </button>
                          <button
                            className="rounded-md border border-coral px-3 py-2 text-xs font-semibold text-coral"
                            onClick={() =>
                              extensionDecisionMutation.mutate({
                                extensionId: extension.id,
                                decision: "reject"
                              })
                            }
                          >
                            Reject
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))}
                {extensions.data?.length === 0 ? (
                  <p className="text-sm text-slate-500">No extension requests.</p>
                ) : null}
              </div>
            </Panel>
          ) : null}
        </section>

        <aside className="grid content-start gap-5">
          <Panel title="Notifications" icon={Bell}>
            <div className="grid gap-2">
              {(notifications.data ?? []).slice(0, 6).map((notification) => (
                <button
                  key={notification.id}
                  className={`rounded-md border border-line p-3 text-left text-sm transition hover:bg-panel ${
                    notification.read_at ? "bg-white text-slate-500" : "bg-panel text-ink"
                  }`}
                  onClick={() => readNotificationMutation.mutate(notification.id)}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold">
                      {notification.event_type.replaceAll("_", " ")}
                    </span>
                    <span className="text-xs text-slate-500">
                      {new Date(notification.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="mt-1 text-slate-600">{notification.message}</p>
                </button>
              ))}
              {notifications.data?.length === 0 ? (
                <p className="text-sm text-slate-500">No notifications for this identity.</p>
              ) : null}
              {notifications.isError ? (
                <p className="text-sm text-coral">Notifications unavailable.</p>
              ) : null}
            </div>
          </Panel>

          <Panel title="New Request" icon={CloudCog}>
            <form
              className="grid gap-3"
              onSubmit={form.handleSubmit((values) => createMutation.mutate(values))}
            >
              <TextInput label="Project name" {...form.register("project_name")} />
              <TextArea label="Business justification" {...form.register("business_justification")} />
              <div className="grid grid-cols-2 gap-3">
                <TextInput label="Sponsor" {...form.register("project_sponsor")} />
                <TextInput label="Cost center" {...form.register("cost_center")} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <TextInput label="Budget" type="number" {...form.register("requested_budget")} />
                <TextInput label="Users" type="number" {...form.register("expected_users")} />
              </div>
              <label className="grid gap-1 text-sm font-medium">
                Data class
                <select className="h-10 rounded-md border border-line px-3" {...form.register("data_classification")}>
                  <option value="public">public</option>
                  <option value="internal">internal</option>
                  <option value="confidential">confidential</option>
                  <option value="regulated">regulated</option>
                  <option value="restricted">restricted</option>
                </select>
              </label>
              <div className="grid gap-2">
                <span className="text-sm font-medium">Providers</span>
                <div className="grid grid-cols-2 gap-2">
                  {providerOptions.map((provider) => (
                    <label key={provider} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" value={provider} {...form.register("requested_providers")} />
                      <span>{provider.replaceAll("_", " ")}</span>
                    </label>
                  ))}
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" {...form.register("uses_source_code")} />
                Proprietary source code
              </label>
              <TextInput label="Usage pattern" {...form.register("expected_usage_pattern")} />
              <TextInput
                label="Monthly volume"
                type="number"
                {...form.register("estimated_monthly_volume")}
              />
              <input
                type="hidden"
                {...form.register("requested_start_at")}
                defaultValue={defaultValues.requested_start_at}
              />
              <input
                type="hidden"
                {...form.register("requested_end_at")}
                defaultValue={defaultValues.requested_end_at}
              />
              <input type="hidden" {...form.register("currency")} defaultValue="USD" />
              <button
                data-testid="submit-request"
                className="h-10 rounded-md bg-ink px-4 text-sm font-semibold text-white disabled:opacity-60"
                disabled={createMutation.isPending}
              >
                Submit Request
              </button>
              {Object.keys(form.formState.errors).length > 0 ? (
                <p className="text-sm text-coral" data-testid="form-errors">
                  Check the request details before submitting.
                </p>
              ) : null}
              {createMutation.error ? (
                <p className="text-sm text-coral">{createMutation.error.message}</p>
              ) : null}
            </form>
          </Panel>

          <Panel title="Approval Queue" icon={CheckCircle2}>
            <div className="grid gap-3">
              {(approvals.data ?? []).map((step) => (
                <div key={step.step_id} className="rounded-md border border-line p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold">{step.step_type}</p>
                      <p className="break-all text-xs text-slate-500">{step.request_id}</p>
                    </div>
                    <div className="flex gap-2">
                      <button
                        data-testid={`approve-${step.step_type}`}
                        className="rounded-md bg-mint px-3 py-2 text-xs font-semibold text-white"
                        onClick={() =>
                          approvalMutation.mutate({ stepId: step.step_id, decision: "approve" })
                        }
                      >
                        Approve
                      </button>
                      <button
                        className="rounded-md border border-coral px-3 py-2 text-xs font-semibold text-coral"
                        onClick={() =>
                          approvalMutation.mutate({ stepId: step.step_id, decision: "reject" })
                        }
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              {approvals.isError ? (
                <p className="text-sm text-slate-500">Queue unavailable for this identity.</p>
              ) : null}
              {approvals.data?.length === 0 ? (
                <p className="text-sm text-slate-500">No pending approvals.</p>
              ) : null}
            </div>
          </Panel>
        </aside>
      </div>
    </main>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  tone = "ink"
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  tone?: "ink" | "mint" | "amber";
}) {
  const color = tone === "mint" ? "text-mint" : tone === "amber" ? "text-amber" : "text-ink";
  return (
    <div className="rounded-md border border-line bg-white p-4 shadow-quiet">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-slate-500">{label}</span>
        <Icon className={`h-5 w-5 ${color}`} aria-hidden />
      </div>
      <p className="mt-3 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function Panel({
  title,
  icon: Icon,
  children
}: {
  title: string;
  icon: typeof Activity;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-line bg-white p-4 shadow-quiet">
      <div className="mb-4 flex items-center gap-2">
        <Icon className="h-5 w-5 text-mint" aria-hidden />
        <h2 className="text-base font-semibold">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function StatusPill({ status }: { status: AccessRequest["status"] | string }) {
  const className = status === "ACTIVE" ? "bg-mint/10 text-mint" : "bg-amber/10 text-amber";
  return (
    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${className}`}>
      <span className="sr-only" data-testid={`status-${status}`} />
      {status.replaceAll("_", " ")}
    </span>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-panel p-3">
      <p className="text-xs font-medium uppercase text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  );
}

function ActionButton({
  icon: Icon,
  label,
  testId,
  onClick
}: {
  icon: typeof Activity;
  label: string;
  testId?: string;
  onClick: () => void;
}) {
  return (
    <button
      data-testid={testId}
      className="inline-flex h-9 items-center justify-center gap-1 rounded-md border border-line px-2 text-xs font-semibold hover:bg-panel"
      type="button"
      onClick={onClick}
      title={label}
    >
      <Icon className="h-4 w-4" aria-hidden />
      <span>{label}</span>
    </button>
  );
}

const TextInput = ({
  label,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) => (
  <label className="grid gap-1 text-sm font-medium">
    {label}
    <input className="h-10 rounded-md border border-line px-3" {...props} />
  </label>
);

const TextArea = ({
  label,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) => (
  <label className="grid gap-1 text-sm font-medium">
    {label}
    <textarea className="min-h-20 rounded-md border border-line px-3 py-2" {...props} />
  </label>
);
