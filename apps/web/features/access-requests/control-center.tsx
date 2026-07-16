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
  ExternalLink,
  FileClock,
  LineChart,
  RotateCcw,
  ShieldCheck,
  UserPlus,
  UserRound,
  Zap
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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

import { evidencePanelState } from "@/lib/evidence-state";
import { approvalQueuePanelState } from "@/lib/approval-queue-state";
import { notificationPanelState } from "@/lib/notification-state";
import {
  acceptReassignment,
  addProjectMember,
  apiDocsUrl,
  cancelAccessRequest,
  createAccessRequest,
  createExtensionRequest,
  createReassignment,
  decideReassignment,
  decideExtension,
  decideApproval,
  enforceArchiveRetention,
  expireAssignment,
  exportAdoptionReport,
  exportAuditEvents,
  exportCostAllocation,
  exportExecutiveReport,
  getAdoptionReport,
  getAuditEventSummary,
  getExecutiveReport,
  getMe,
  getOperationalHealth,
  getPolicyEvaluation,
  getRetentionPolicy,
  listArchives,
  listApprovalHistory,
  listAssignments,
  listAuditEvents,
  listBudgetSummaries,
  listCostAllocationDeliveries,
  listCostRecords,
  listExtensions,
  listIncidents,
  listIntegrationCredentials,
  listLifecycleJobs,
  listNotifications,
  listPolicies,
  listPendingApprovals,
  listProvisioningEvidence,
  listProjectAuditEvents,
  listProviderConfiguration,
  listProviderAssignments,
  listProviderHealth,
  listProjectMembers,
  listProjects,
  listReassignments,
  listRequests,
  listRoleChanges,
  listUsageRecords,
  markAllNotificationsRead,
  markNotificationRead,
  overrideApproval,
  publishInternalSecurityReviewPolicy,
  respondToInformationRequest,
  restoreAssignment,
  rotateIntegrationCredential,
  retryLifecycleJob,
  resolveIncident,
  scheduleCostAllocationDelivery,
  scanExpirationWarnings,
  simulateUsage,
  suspendProject,
  updateRetentionPolicy,
  type AccessRequest,
  type ApiIdentity,
  type DevUser
} from "@/lib/api";
import {
  authMode,
  beginOidcLogin,
  clearOidcSession,
  completeOidcLogin,
  loadOidcSession,
  logoutOidcSession,
  oidcConfig,
  refreshOidcSession,
  type OidcSession
} from "@/lib/auth";
import {
  accessRequestSchema,
  providerOptions,
  type AccessRequestFormValues
} from "@/lib/request-schema";

const users: DevUser[] = [
  "employee@example.local",
  "owner@example.local",
  "owner2@example.local",
  "approver@example.local",
  "security@example.local",
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

function payloadValue(payload: Record<string, unknown>, key: string) {
  const value = payload[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function failureSummary(failure: Record<string, unknown>) {
  const message = failure.message;
  if (typeof message === "string" && message.length > 0) {
    return message;
  }
  const details = failure.details;
  if (details && typeof details === "object" && "code" in details) {
    const code = (details as Record<string, unknown>).code;
    return typeof code === "string" ? code : null;
  }
  return null;
}

function compactMetadata(metadata: Record<string, unknown>) {
  const entries = Object.entries(metadata).filter(([, value]) => value !== null && value !== "");
  if (entries.length === 0) {
    return null;
  }
  return entries
    .slice(0, 3)
    .map(([key, value]) => {
      const displayValue = Array.isArray(value) ? value.join(", ") : String(value);
      return `${key}: ${displayValue}`;
    })
    .join(" · ");
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
  const [oidcSession, setOidcSession] = useState<OidcSession | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const mode = authMode();
  const config = useMemo(() => oidcConfig(), []);

  useEffect(() => {
    if (mode !== "oidc" || !config) {
      return;
    }
    const existing = loadOidcSession();
    if (existing) {
      setOidcSession(existing);
      return;
    }
    if (!window.location.search.includes("code=")) {
      void refreshOidcSession(config).then((session) => {
        if (session) {
          setOidcSession(session);
        }
      });
      return;
    }
    void completeOidcLogin(window.location.search, config)
      .then((session) => {
        if (session) {
          setOidcSession(session);
          window.history.replaceState({}, document.title, window.location.pathname);
        }
      })
      .catch((error: unknown) => {
        setAuthError(error instanceof Error ? error.message : "OIDC login failed.");
      });
  }, [config, mode]);

  if (mode === "oidc" && !config) {
    return (
      <AuthShell
        title="OIDC is not configured"
        detail="Set the public OIDC authorization endpoint and client ID before using enterprise login."
      />
    );
  }

  if (mode === "oidc" && !oidcSession) {
    const oidcLoginConfig = config;
    if (!oidcLoginConfig) {
      return null;
    }
    return (
      <AuthShell
        title="AI Access Control Center"
        detail={authError ?? "Sign in with your enterprise identity provider."}
        actionLabel={`Sign in with ${oidcLoginConfig.providerLabel}`}
        onAction={() => void beginOidcLogin(oidcLoginConfig)}
      />
    );
  }

  return (
    <ControlCenterExperience
      identity={oidcSession ?? user}
      oidcSession={oidcSession}
      user={user}
      setUser={setUser}
      onLogout={() => {
        if (config) {
          void logoutOidcSession(config);
        } else {
          clearOidcSession();
        }
        setOidcSession(null);
      }}
    />
  );
}

function ControlCenterExperience({
  identity,
  oidcSession,
  user,
  setUser,
  onLogout
}: {
  identity: ApiIdentity;
  oidcSession: OidcSession | null;
  user: DevUser;
  setUser: (user: DevUser) => void;
  onLogout: () => void;
}) {
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [auditEventTypeFilter, setAuditEventTypeFilter] = useState("");
  const [auditCorrelationFilter, setAuditCorrelationFilter] = useState("");
  const queryClient = useQueryClient();
  const identityKey = typeof identity === "string" ? identity : identity.email;
  const auditFilters = {
    event_type: auditEventTypeFilter.trim() || undefined,
    correlation_id: auditCorrelationFilter.trim() || undefined
  };
  const me = useQuery({ queryKey: ["me", identityKey], queryFn: () => getMe(identity) });
  const roles = me.data?.roles ?? [];
  const isPlatformAdmin = roles.includes("platform_admin");
  const isSecurityAuditor = roles.includes("security_auditor");
  const isCto = roles.includes("cto");
  const canReviewApprovals =
    roles.includes("approver") || roles.includes("security_reviewer") || isCto;
  const canReadPrivilegedEvidence = isPlatformAdmin || isSecurityAuditor || isCto;
  const requests = useQuery({ queryKey: ["requests", identityKey], queryFn: () => listRequests(identity) });
  const projects = useQuery({ queryKey: ["projects", identityKey], queryFn: () => listProjects(identity) });
  const approvals = useQuery({
    queryKey: ["approvals", identityKey],
    queryFn: () => listPendingApprovals(identity),
    enabled: canReviewApprovals,
    retry: false
  });
  const approvalHistory = useQuery({
    queryKey: ["approval-history", identityKey],
    queryFn: () => listApprovalHistory(identity),
    enabled: canReadPrivilegedEvidence,
    retry: false
  });
  const providerHealth = useQuery({
    queryKey: ["provider-health", identityKey],
    queryFn: () => listProviderHealth(identity),
    retry: false
  });
  const providerConfiguration = useQuery({
    queryKey: ["provider-configuration", identityKey],
    queryFn: () => listProviderConfiguration(identity),
    enabled: canReadPrivilegedEvidence,
    retry: false
  });
  const integrationCredentials = useQuery({
    queryKey: ["integration-credentials", identityKey],
    queryFn: () => listIntegrationCredentials(identity),
    enabled: canReadPrivilegedEvidence,
    retry: false
  });
  const assignments = useQuery({
    queryKey: ["assignments", identityKey],
    queryFn: () => listAssignments(identity),
    enabled: isPlatformAdmin,
    retry: false
  });
  const providerAssignments = useQuery({
    queryKey: ["provider-assignments", identityKey],
    queryFn: () => listProviderAssignments(identity),
    retry: false
  });
  const usageRecords = useQuery({
    queryKey: ["usage-records", identityKey],
    queryFn: () => listUsageRecords(identity),
    retry: false
  });
  const costRecords = useQuery({
    queryKey: ["cost-records", identityKey],
    queryFn: () => listCostRecords(identity),
    retry: false
  });
  const budgetSummaries = useQuery({
    queryKey: ["budget-summaries", identityKey],
    queryFn: () => listBudgetSummaries(identity),
    retry: false
  });
  const archives = useQuery({
    queryKey: ["archives", identityKey],
    queryFn: () => listArchives(identity),
    enabled: isPlatformAdmin,
    retry: false
  });
  const lifecycleJobs = useQuery({
    queryKey: ["lifecycle-jobs", identityKey],
    queryFn: () => listLifecycleJobs(identity),
    enabled: isPlatformAdmin,
    retry: false
  });
  const auditEvents = useQuery({
    queryKey: ["audit-events", identityKey, auditFilters.event_type, auditFilters.correlation_id],
    queryFn: () => listAuditEvents(identity, auditFilters),
    enabled: isSecurityAuditor,
    retry: false
  });
  const auditSummary = useQuery({
    queryKey: ["audit-summary", identityKey, auditFilters.event_type, auditFilters.correlation_id],
    queryFn: () => getAuditEventSummary(identity, auditFilters),
    enabled: isSecurityAuditor,
    retry: false
  });
  const notifications = useQuery({
    queryKey: ["notifications", identityKey],
    queryFn: () => listNotifications(identity),
    retry: false
  });
  const executiveReport = useQuery({
    queryKey: ["executive-report", identityKey],
    queryFn: () => getExecutiveReport(identity),
    enabled: isCto,
    retry: false
  });
  const adoptionReport = useQuery({
    queryKey: ["adoption-report", identityKey],
    queryFn: () => getAdoptionReport(identity),
    enabled: canReadPrivilegedEvidence,
    retry: false
  });
  const costAllocationDeliveries = useQuery({
    queryKey: ["cost-allocation-deliveries", identityKey],
    queryFn: () => listCostAllocationDeliveries(identity),
    enabled: canReadPrivilegedEvidence,
    retry: false
  });
  const incidents = useQuery({
    queryKey: ["incidents", identityKey],
    queryFn: () => listIncidents(identity),
    enabled: canReadPrivilegedEvidence,
    retry: false
  });
  const operationalHealth = useQuery({
    queryKey: ["operational-health", identityKey],
    queryFn: () => getOperationalHealth(identity),
    enabled: canReadPrivilegedEvidence,
    retry: false
  });
  const provisioningEvidence = useQuery({
    queryKey: ["provisioning-evidence", identityKey],
    queryFn: () => listProvisioningEvidence(identity),
    enabled: canReadPrivilegedEvidence,
    retry: false
  });
  const policies = useQuery({
    queryKey: ["policies", identityKey],
    queryFn: () => listPolicies(identity),
    enabled: isPlatformAdmin || isSecurityAuditor,
    retry: false
  });
  const retentionPolicy = useQuery({
    queryKey: ["retention-policy", identityKey],
    queryFn: () => getRetentionPolicy(identity),
    enabled: isPlatformAdmin || isSecurityAuditor,
    retry: false
  });
  const extensions = useQuery({
    queryKey: ["extensions", identityKey],
    queryFn: () => listExtensions(identity),
    retry: false
  });
  const reassignments = useQuery({
    queryKey: ["reassignments", identityKey],
    queryFn: () => listReassignments(identity),
    retry: false
  });
  const roleChanges = useQuery({
    queryKey: ["role-changes", identityKey],
    queryFn: () => listRoleChanges(identity),
    enabled: canReadPrivilegedEvidence,
    retry: false
  });
  const selectedRequest = useMemo(
    () => requests.data?.find((request) => request.id === selectedRequestId) ?? requests.data?.[0],
    [requests.data, selectedRequestId]
  );
  const requestById = useMemo(
    () => new Map((requests.data ?? []).map((request) => [request.id, request])),
    [requests.data]
  );
  const selectedRequestProjectId = selectedRequest?.project_id;
  const selectedProjectId = projects.data?.some((project) => project.id === selectedRequestProjectId)
    ? selectedRequestProjectId
    : projects.data?.[0]?.id;
  const showProjectAudit = !isSecurityAuditor;
  const projectMembers = useQuery({
    queryKey: ["project-members", identityKey, selectedProjectId],
    queryFn: () => listProjectMembers(identity, selectedProjectId ?? ""),
    enabled: Boolean(selectedProjectId),
    retry: false
  });
  const projectAuditEvents = useQuery({
    queryKey: ["project-audit-events", identityKey, selectedProjectId],
    queryFn: () => listProjectAuditEvents(identity, selectedProjectId ?? ""),
    enabled: Boolean(selectedProjectId) && showProjectAudit,
    retry: false
  });
  const evaluation = useQuery({
    queryKey: ["policy-evaluation", identityKey, selectedRequest?.id],
    queryFn: () => getPolicyEvaluation(identity, selectedRequest?.id ?? ""),
    enabled: Boolean(selectedRequest?.id)
  });

  const form = useForm<AccessRequestFormValues>({
    resolver: zodResolver(accessRequestSchema),
    defaultValues,
    shouldUnregister: false
  });

  const createMutation = useMutation({
    mutationFn: (values: AccessRequestFormValues) => createAccessRequest(identity, values),
    onSuccess: (created) => {
      setSelectedRequestId(created.id);
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["project-members"] });
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
      void queryClient.invalidateQueries({ queryKey: ["assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["budget-summaries"] });
      void queryClient.invalidateQueries({ queryKey: ["lifecycle-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  });

  const approvalMutation = useMutation({
    mutationFn: ({
      stepId,
      decision
    }: {
      stepId: string;
      decision: "approve" | "reject" | "request_information";
    }) =>
      decideApproval(identity, stepId, decision),
    onSuccess: (updated) => {
      setSelectedRequestId(updated.id);
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
      void queryClient.invalidateQueries({ queryKey: ["approval-history"] });
      void queryClient.invalidateQueries({ queryKey: ["policy-evaluation"] });
      void queryClient.invalidateQueries({ queryKey: ["assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["budget-summaries"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  });
  const overrideMutation = useMutation({
    mutationFn: ({
      requestId,
      decision
    }: {
      requestId: string;
      decision: "approve" | "reject";
    }) => overrideApproval(identity, requestId, decision),
    onSuccess: (updated) => {
      setSelectedRequestId(updated.id);
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
      void queryClient.invalidateQueries({ queryKey: ["approval-history"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["budget-summaries"] });
      void queryClient.invalidateQueries({ queryKey: ["lifecycle-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const informationResponseMutation = useMutation({
    mutationFn: (requestId: string) => respondToInformationRequest(identity, requestId),
    onSuccess: (updated) => {
      setSelectedRequestId(updated.id);
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const cancelMutation = useMutation({
    mutationFn: (requestId: string) => cancelAccessRequest(identity, requestId),
    onSuccess: (updated) => {
      setSelectedRequestId(updated.id);
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["budget-summaries"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  });
  const addProjectMemberMutation = useMutation({
    mutationFn: (projectId: string) => addProjectMember(identity, projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["project-members"] });
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const suspendProjectMutation = useMutation({
    mutationFn: (projectId: string) => suspendProject(identity, projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["executive-report"] });
    }
  });
  const createReassignmentMutation = useMutation({
    mutationFn: (projectId: string) => createReassignment(identity, projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reassignments"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const acceptReassignmentMutation = useMutation({
    mutationFn: (reassignmentId: string) => acceptReassignment(identity, reassignmentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reassignments"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const reassignmentDecisionMutation = useMutation({
    mutationFn: ({
      reassignmentId,
      decision
    }: {
      reassignmentId: string;
      decision: "approve" | "reject";
    }) => decideReassignment(identity, reassignmentId, decision),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reassignments"] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["project-members"] });
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
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
        return restoreAssignment(identity, assignmentId);
      }
      if (action === "expire") {
        return expireAssignment(identity, assignmentId);
      }
      return simulateUsage(identity, assignmentId, action);
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
      void queryClient.invalidateQueries({ queryKey: ["lifecycle-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["incidents"] });
    }
  });
  const retryLifecycleJobMutation = useMutation({
    mutationFn: (jobId: string) => retryLifecycleJob(identity, jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["lifecycle-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const expirationWarningMutation = useMutation({
    mutationFn: () => scanExpirationWarnings(identity),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["lifecycle-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const readNotificationMutation = useMutation({
    mutationFn: (notificationId: string) => markNotificationRead(identity, notificationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const readAllNotificationsMutation = useMutation({
    mutationFn: () => markAllNotificationsRead(identity),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const auditExportMutation = useMutation({
    mutationFn: () => exportAuditEvents(identity, auditFilters),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const retentionEnforcementMutation = useMutation({
    mutationFn: () => enforceArchiveRetention(identity),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["archives"] });
      void queryClient.invalidateQueries({ queryKey: ["lifecycle-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });

  const costAllocationExportMutation = useMutation({
    mutationFn: () => exportCostAllocation(identity)
  });
  const executiveReportExportMutation = useMutation({
    mutationFn: () => exportExecutiveReport(identity),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const adoptionReportExportMutation = useMutation({
    mutationFn: () => exportAdoptionReport(identity),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });

  const costAllocationDeliveryMutation = useMutation({
    mutationFn: () => scheduleCostAllocationDelivery(identity),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cost-allocation-deliveries"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const extensionMutation = useMutation({
    mutationFn: ({ requestId, currentEndAt }: { requestId: string; currentEndAt: string }) =>
      createExtensionRequest(identity, requestId, currentEndAt),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["extensions"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  });
  const extensionDecisionMutation = useMutation({
    mutationFn: ({ extensionId, decision }: { extensionId: string; decision: "approve" | "reject" }) =>
      decideExtension(identity, extensionId, decision),
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
    mutationFn: (incidentId: string) => resolveIncident(identity, incidentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["incidents"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const policyPublishMutation = useMutation({
    mutationFn: () => {
      const activePolicy = policies.data?.find((policy) => policy.active);
      if (!activePolicy) {
        throw new Error("No active policy version found.");
      }
      return publishInternalSecurityReviewPolicy(identity, activePolicy);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["policies"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const retentionPolicyMutation = useMutation({
    mutationFn: () => updateRetentionPolicy(identity),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["retention-policy"] });
      void queryClient.invalidateQueries({ queryKey: ["policies"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });
  const credentialRotationMutation = useMutation({
    mutationFn: (credentialId: string) => rotateIntegrationCredential(identity, credentialId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["integration-credentials"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-events"] });
      void queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    }
  });

  const activeRequests = requests.data?.filter((request) => request.status === "ACTIVE").length ?? 0;
  const pendingRequests =
    requests.data?.filter((request) => request.status.includes("AWAITING")).length ?? 0;
  const unreadNotifications =
    notifications.data?.filter((notification) => !notification.read_at).length ?? 0;
  const notificationsState = notificationPanelState({
    count: notifications.data?.length,
    isError: notifications.isError,
    isLoading: notifications.isLoading
  });
  const latestUsage = usageRecords.data?.[0];
  const latestCost = costRecords.data?.[0];
  const visibleAssignments = providerAssignments.data?.length ?? 0;
  const budgetEvidenceState = evidencePanelState({
    count: budgetSummaries.data?.length,
    isError: budgetSummaries.isError || usageRecords.isError || costRecords.isError,
    isLoading: budgetSummaries.isLoading || usageRecords.isLoading || costRecords.isLoading
  });
  const healthyProviders =
    providerHealth.data?.filter((provider) => provider.status === "healthy").length ?? 0;
  const totalProviders = providerHealth.data?.length ?? 0;
  const allProvidersHealthy = totalProviders > 0 && healthyProviders === totalProviders;
  const providerHealthState = evidencePanelState({
    count: providerHealth.data?.length,
    isError: providerHealth.isError,
    isLoading: providerHealth.isLoading
  });
  const approvalQueueState = approvalQueuePanelState({
    canReviewApprovals,
    count: approvals.data?.length,
    isError: approvals.isError,
    isLoading: approvals.isLoading
  });
  const reassignmentState = evidencePanelState({
    count: reassignments.data?.length,
    isError: reassignments.isError,
    isLoading: reassignments.isLoading
  });
  const activePolicy = policies.data?.find((policy) => policy.active);
  const policyState = evidencePanelState({
    count: activePolicy || retentionPolicy.data ? 1 : policies.data?.length,
    isError: policies.isError || retentionPolicy.isError,
    isLoading: policies.isLoading || retentionPolicy.isLoading
  });
  const incidentsState = evidencePanelState({
    count: incidents.data?.length,
    isError: incidents.isError,
    isLoading: incidents.isLoading
  });
  const approvalHistoryState = evidencePanelState({
    count: approvalHistory.data?.length,
    isError: approvalHistory.isError,
    isLoading: approvalHistory.isLoading
  });
  const roleChangesState = evidencePanelState({
    count: roleChanges.data?.length,
    isError: roleChanges.isError,
    isLoading: roleChanges.isLoading
  });
  const operationalHealthState = evidencePanelState({
    count: operationalHealth.data ? 1 : 0,
    isError: operationalHealth.isError,
    isLoading: operationalHealth.isLoading
  });
  const provisioningEvidenceState = evidencePanelState({
    count: provisioningEvidence.data?.length,
    isError: provisioningEvidence.isError,
    isLoading: provisioningEvidence.isLoading
  });
  const auditTrailState = evidencePanelState({
    count: auditEvents.data?.length,
    isError: auditEvents.isError,
    isLoading: auditEvents.isLoading
  });
  const executiveReportState = evidencePanelState({
    count: executiveReport.data ? 1 : 0,
    isError: executiveReport.isError,
    isLoading: executiveReport.isLoading
  });
  const executiveProviderChartData = useMemo(
    () =>
      (executiveReport.data?.spend_by_provider ?? []).map((provider) => ({
        provider: provider.provider.replaceAll("_", " "),
        spend: Number(provider.spend),
        tokens: provider.tokens,
        activeAssignments: provider.active_assignments
      })),
    [executiveReport.data?.spend_by_provider]
  );
  const executiveCostCenterChartData = useMemo(
    () =>
      (executiveReport.data?.spend_by_cost_center ?? []).map((center) => ({
        costCenter: center.cost_center,
        budget: Number(center.budget),
        spend: Number(center.spend),
        remaining: Number(center.remaining_budget)
      })),
    [executiveReport.data?.spend_by_cost_center]
  );
  const adoptionReportState = evidencePanelState({
    count: adoptionReport.data ? 1 : 0,
    isError: adoptionReport.isError,
    isLoading: adoptionReport.isLoading
  });
  const adoptionProviderChartData = useMemo(
    () =>
      (adoptionReport.data?.adoption_by_provider ?? []).map((provider) => ({
        provider: provider.name.replaceAll("_", " "),
        activeAssignments: provider.active_assignments,
        requestCount: provider.request_count,
        tokens: provider.total_tokens
      })),
    [adoptionReport.data?.adoption_by_provider]
  );
  const extensionQueueState = evidencePanelState({
    count: extensions.data?.length,
    isError: extensions.isError,
    isLoading: extensions.isLoading
  });
  const canManageSelectedProject =
    me.data?.roles.some((role) => role === "project_owner" || role === "platform_admin") ?? false;
  const securityAlreadyMember =
    projectMembers.data?.some((member) => member.email === "security@example.local") ?? false;
  const pendingSelectedReassignment = reassignments.data?.find(
    (reassignment) =>
      reassignment.project_id === selectedProjectId &&
      ["pending_acceptance", "pending_approval"].includes(reassignment.status)
  );

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
          {oidcSession ? (
            <div className="flex flex-wrap items-center gap-3 text-sm font-medium text-slate-700">
              <a
                href={apiDocsUrl()}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 shadow-quiet"
              >
                <ExternalLink className="h-4 w-4" aria-hidden />
                API Docs
              </a>
              <UserRound className="h-4 w-4" aria-hidden />
              <span>{oidcSession.email}</span>
              <button
                type="button"
                className="h-10 rounded-md border border-line bg-white px-3 shadow-quiet"
                onClick={onLogout}
              >
                Sign out
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3 text-sm font-medium text-slate-700">
              <a
                href={apiDocsUrl()}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 shadow-quiet"
              >
                <ExternalLink className="h-4 w-4" aria-hidden />
                API Docs
              </a>
              <label className="flex items-center gap-2">
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
          )}
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
              {providerHealthState === "loading" ? (
                <p className="text-sm text-slate-500">Loading provider checks...</p>
              ) : null}
              {providerHealthState === "error" ? (
                <p className="text-sm text-coral">
                  Provider checks could not be loaded. Check that the API is running for this
                  dashboard session.
                </p>
              ) : null}
              {providerHealthState === "empty" ? (
                <p className="text-sm text-slate-500">
                  No provider checks have been recorded yet.
                </p>
              ) : null}
              {providerHealthState === "ready"
                ? (providerHealth.data ?? []).map((provider) => (
                    <div
                      key={provider.provider}
                      className="rounded-md border border-line p-3 text-sm"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-semibold">{provider.provider.replaceAll("_", " ")}</p>
                        <StatusPill status={provider.status} />
                      </div>
                      <p className="mt-2 text-xs text-slate-500">
                        {provider.latency_ms}ms · {String(provider.details.mode ?? "unknown")}
                      </p>
                    </div>
                  ))
                : null}
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
            {integrationCredentials.data ? (
              <div className="mt-4 grid gap-2 border-t border-line pt-4">
                {integrationCredentials.data.slice(0, 4).map((credential) => (
                  <div
                    key={credential.id}
                    className="grid gap-2 rounded-md border border-line p-3 text-sm"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold">
                        {credential.provider.replaceAll("_", " ")}
                      </span>
                      {user === "admin@example.local" ? (
                        <button
                          type="button"
                          className="h-8 rounded-md border border-line bg-white px-2 text-xs font-semibold text-ink shadow-quiet disabled:cursor-not-allowed disabled:opacity-60"
                          onClick={() => credentialRotationMutation.mutate(credential.id)}
                          disabled={credentialRotationMutation.isPending}
                        >
                          Rotate
                        </button>
                      ) : null}
                    </div>
                    <p className="break-all text-xs text-slate-500">
                      {credential.credential_reference}
                    </p>
                    <p className="text-xs text-slate-500">
                      Rotation due{" "}
                      {credential.rotation_due_at
                        ? new Date(credential.rotation_due_at).toLocaleDateString()
                        : "not scheduled"}
                    </p>
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
                    <div className="flex items-center gap-2">
                      <StatusPill status={project.status} />
                      {(user === "cto@example.local" || user === "admin@example.local") &&
                      project.status !== "suspended" ? (
                        <button
                          type="button"
                          className="h-8 rounded-md border border-line bg-white px-2 text-xs font-semibold text-ink shadow-quiet disabled:cursor-not-allowed disabled:opacity-60"
                          onClick={() => suspendProjectMutation.mutate(project.id)}
                          disabled={suspendProjectMutation.isPending}
                        >
                          Suspend
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
              {projectMembers.data && projectMembers.data.length > 0 ? (
                <div className="rounded-md border border-line bg-panel p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold">Project members</p>
                    {canManageSelectedProject && selectedProjectId && !securityAlreadyMember ? (
                      <button
                        type="button"
                        className="inline-flex h-8 items-center gap-2 rounded-md border border-line bg-white px-2 text-xs font-semibold text-ink shadow-quiet disabled:cursor-not-allowed disabled:opacity-60"
                        onClick={() => addProjectMemberMutation.mutate(selectedProjectId)}
                        disabled={addProjectMemberMutation.isPending}
                      >
                        <UserPlus className="h-4 w-4" aria-hidden />
                        Add Sam
                      </button>
                    ) : null}
                    {user === "owner@example.local" &&
                    selectedProjectId &&
                    !pendingSelectedReassignment ? (
                      <button
                        type="button"
                        className="inline-flex h-8 items-center gap-2 rounded-md border border-line bg-white px-2 text-xs font-semibold text-ink shadow-quiet disabled:cursor-not-allowed disabled:opacity-60"
                        onClick={() => createReassignmentMutation.mutate(selectedProjectId)}
                        disabled={createReassignmentMutation.isPending}
                      >
                        <UserRound className="h-4 w-4" aria-hidden />
                        Reassign
                      </button>
                    ) : null}
                  </div>
                  {addProjectMemberMutation.isSuccess ? (
                    <p className="mt-2 text-xs text-emerald-700">Project member added.</p>
                  ) : null}
                  {createReassignmentMutation.isSuccess ? (
                    <p className="mt-2 text-xs text-emerald-700">Reassignment requested.</p>
                  ) : null}
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
              {showProjectAudit && projectAuditEvents.data && projectAuditEvents.data.length > 0 ? (
                <div className="rounded-md border border-line bg-panel p-3 text-sm">
                  <p className="font-semibold">Project audit</p>
                  <div className="mt-2 grid gap-2">
                    {projectAuditEvents.data.slice(0, 4).map((event) => (
                      <div key={event.id} className="rounded-md border border-line bg-white p-2">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-semibold">{event.event_type}</span>
                          <span className="text-xs text-slate-500">
                            {new Date(event.created_at).toLocaleTimeString()}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          {event.action} · {event.result}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          Target: {event.target_type}
                          {event.target_id ? `/${event.target_id.slice(0, 8)}` : ""} ·
                          Correlation: {event.correlation_id}
                        </p>
                        {compactMetadata(event.metadata_json) ? (
                          <p className="mt-1 text-xs text-slate-600">
                            {compactMetadata(event.metadata_json)}
                          </p>
                        ) : null}
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

          <Panel title="Reassignments" icon={UserRound}>
            <div className="grid gap-2">
              {reassignmentState === "loading" ? (
                <p className="text-sm text-slate-500">Loading reassignment activity...</p>
              ) : null}
              {reassignmentState === "error" ? (
                <p className="text-sm text-coral">
                  Reassignment activity could not be loaded. Check that the API is running for this
                  dashboard session.
                </p>
              ) : null}
              {reassignmentState === "empty" ? (
                <p className="text-sm text-slate-500">No reassignment activity for this identity.</p>
              ) : null}
              {reassignmentState === "ready"
                ? (reassignments.data ?? []).slice(0, 5).map((reassignment) => (
                    <div
                      key={reassignment.id}
                      className="rounded-md border border-line p-3 text-sm"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-semibold">{reassignment.project_name}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            {reassignment.current_owner_email} →{" "}
                            {reassignment.proposed_owner_email}
                          </p>
                        </div>
                        <StatusPill status={reassignment.status} />
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {user === "owner2@example.local" &&
                        reassignment.status === "pending_acceptance" ? (
                          <button
                            className="rounded-md border border-line px-3 py-2 text-xs font-semibold"
                            onClick={() => acceptReassignmentMutation.mutate(reassignment.id)}
                          >
                            Accept
                          </button>
                        ) : null}
                        {(user === "admin@example.local" || user === "cto@example.local") &&
                        reassignment.status === "pending_approval" ? (
                          <>
                            <button
                              className="rounded-md bg-mint px-3 py-2 text-xs font-semibold text-white"
                              onClick={() =>
                                reassignmentDecisionMutation.mutate({
                                  reassignmentId: reassignment.id,
                                  decision: "approve"
                                })
                              }
                            >
                              Approve
                            </button>
                            <button
                              className="rounded-md border border-coral px-3 py-2 text-xs font-semibold text-coral"
                              onClick={() =>
                                reassignmentDecisionMutation.mutate({
                                  reassignmentId: reassignment.id,
                                  decision: "reject"
                                })
                              }
                            >
                              Reject
                            </button>
                          </>
                        ) : null}
                      </div>
                    </div>
                  ))
                : null}
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
                        {user === "employee@example.local" && request.status === "SUBMITTED" ? (
                          <button
                            className="rounded-md border border-line px-2 py-1 text-xs font-semibold"
                            onClick={(event) => {
                              event.stopPropagation();
                              informationResponseMutation.mutate(request.id);
                            }}
                          >
                            Send Info
                          </button>
                        ) : null}
                        {user === "cto@example.local" &&
                        !["ACTIVE", "CLOSED", "CANCELLED", "EXPIRED", "SUSPENDED"].includes(
                          request.status
                        ) ? (
                          <button
                            className="rounded-md border border-line px-2 py-1 text-xs font-semibold"
                            onClick={(event) => {
                              event.stopPropagation();
                              overrideMutation.mutate({
                                requestId: request.id,
                                decision: "approve"
                              });
                            }}
                          >
                            Override
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
                {budgetEvidenceState === "loading" ? (
                  <p className="text-sm text-slate-500">Loading usage and budget evidence...</p>
                ) : null}
                {budgetEvidenceState === "error" ? (
                  <p className="text-sm text-coral">
                    Usage and budget evidence could not be loaded. Check that the API is running
                    for this dashboard session.
                  </p>
                ) : null}
                {budgetEvidenceState === "empty" ? (
                  <p className="text-sm text-slate-500">
                    Budget evidence will appear after a request is submitted.
                  </p>
                ) : null}
                {budgetEvidenceState === "ready"
                  ? (budgetSummaries.data ?? []).slice(0, 4).map((summary) => (
                      <div
                        key={summary.request_id}
                        className="rounded-md border border-line p-3 text-sm"
                      >
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
                              {summary.currency} {summary.total_spend} /{" "}
                              {summary.requested_budget}
                            </p>
                            <p className="text-xs text-slate-500">
                              {summary.utilization_percent}% used · {summary.currency}{" "}
                              {summary.remaining_budget} remaining
                            </p>
                          </div>
                        </div>
                      </div>
                    ))
                  : null}
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
                {assignments.data && assignments.data.length > 0 ? (
                  <div className="rounded-md border border-line bg-panel p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-semibold">Expiration warnings</p>
                        <p className="mt-1 text-xs text-slate-500">
                          Scan active assignments inside the warning window.
                        </p>
                      </div>
                      <ActionButton
                        icon={FileClock}
                        label="Scan"
                        testId="expiration-warning-scan"
                        onClick={() => expirationWarningMutation.mutate()}
                      />
                    </div>
                    {expirationWarningMutation.data ? (
                      <p className="mt-2 text-xs text-slate-500">
                        Warning job {expirationWarningMutation.data.status} · notified{" "}
                        {String(expirationWarningMutation.data.payload.warned_count ?? 0)}
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {archives.data && archives.data.length > 0 ? (
                  <div className="rounded-md border border-line bg-panel p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-semibold">Latest archive</p>
                      <ActionButton
                        icon={Archive}
                        label="Retention"
                        onClick={() => retentionEnforcementMutation.mutate()}
                      />
                    </div>
                    <p className="mt-1 break-all text-slate-600">
                      {archives.data[0].storage_location}
                    </p>
                    {retentionEnforcementMutation.data ? (
                      <p className="mt-2 text-xs text-slate-500">
                        Retention job {retentionEnforcementMutation.data.status} · purged{" "}
                        {String(retentionEnforcementMutation.data.payload.purged_count ?? 0)}
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {lifecycleJobs.data && lifecycleJobs.data.length > 0 ? (
                  <div className="rounded-md border border-line bg-panel p-3 text-sm">
                    <p className="font-semibold">Lifecycle jobs</p>
                    <div className="mt-2 grid gap-2">
                      {lifecycleJobs.data.slice(0, 4).map((job) => (
                        <div
                          key={job.id}
                          className="grid gap-2 rounded-md border border-line bg-white p-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-semibold">{job.job_type}</span>
                            <StatusPill status={job.status} />
                          </div>
                          <p className="break-all text-xs text-slate-500">
                            {job.idempotency_key}
                          </p>
                          <div className="grid gap-1 text-xs text-slate-500 sm:grid-cols-2">
                            <span>
                              Provider: {payloadValue(job.payload, "provider") ?? "n/a"}
                            </span>
                            <span>
                              Correlation: {payloadValue(job.payload, "correlation_id") ?? "n/a"}
                            </span>
                          </div>
                          {failureSummary(job.failure_information) ? (
                            <p className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-700">
                              {failureSummary(job.failure_information)}
                            </p>
                          ) : null}
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="text-xs text-slate-500">
                              Attempt {job.attempt_count}
                            </span>
                            {job.status === "failed" || job.status === "queued" ? (
                              <button
                                type="button"
                                className="h-8 rounded-md border border-line bg-white px-2 text-xs font-semibold text-ink shadow-quiet disabled:cursor-not-allowed disabled:opacity-60"
                                onClick={() => retryLifecycleJobMutation.mutate(job.id)}
                                disabled={retryLifecycleJobMutation.isPending}
                              >
                                Retry
                              </button>
                            ) : null}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </Panel>
          ) : null}

          {user === "admin@example.local" || user === "auditor@example.local" ? (
            <Panel title="Policies" icon={ShieldCheck}>
              <div className="grid gap-3 text-sm">
                {policyState === "loading" ? (
                  <p className="text-sm text-slate-500">Loading policy evidence...</p>
                ) : null}
                {policyState === "error" ? (
                  <p className="text-sm text-coral">
                    Policy evidence could not be loaded. Check that the API is running for this
                    dashboard session.
                  </p>
                ) : null}
                {policyState === "empty" ? (
                  <p className="text-sm text-slate-500">No active policy evidence yet.</p>
                ) : null}
                {policyState === "ready" && activePolicy ? (
                  <div className="rounded-md border border-line p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">{activePolicy.name}</p>
                        <p className="mt-1 text-slate-600">
                          Version {activePolicy.version} · active
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
                ) : null}
                {policyPublishMutation.data ? (
                  <p className="rounded-md bg-panel p-2 text-xs text-slate-600">
                    Published policy version {policyPublishMutation.data.version}.
                  </p>
                ) : null}
                {policyState === "ready" && retentionPolicy.data ? (
                  <div className="rounded-md border border-line p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">Artifact retention</p>
                        <p className="mt-1 text-slate-600">
                          {retentionPolicy.data.artifact_retention_days} days · policy version{" "}
                          {retentionPolicy.data.version}
                        </p>
                      </div>
                      {user === "admin@example.local" ? (
                        <button
                          className="rounded-md border border-line px-3 py-2 text-xs font-semibold"
                          onClick={() => retentionPolicyMutation.mutate()}
                        >
                          Set 30 Days
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : null}
                {retentionPolicyMutation.data ? (
                  <p className="rounded-md bg-panel p-2 text-xs text-slate-600">
                    Retention updated to {retentionPolicyMutation.data.artifact_retention_days} days.
                  </p>
                ) : null}
              </div>
            </Panel>
          ) : null}

          {user === "admin@example.local" || user === "auditor@example.local" ? (
            <Panel title="Incidents" icon={AlertTriangle}>
              <div className="grid gap-2">
                {incidentsState === "loading" ? (
                  <p className="text-sm text-slate-500">Loading incidents...</p>
                ) : null}
                {incidentsState === "error" ? (
                  <p className="text-sm text-coral">
                    Incidents could not be loaded. Check that the API is running for this dashboard
                    session.
                  </p>
                ) : null}
                {incidentsState === "empty" ? (
                  <p className="text-sm text-slate-500">No incidents.</p>
                ) : null}
                {incidentsState === "ready"
                  ? (incidents.data ?? []).slice(0, 5).map((incident) => (
                      <div key={incident.id} className="rounded-md border border-line p-3 text-sm">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold">{incident.summary}</p>
                              <StatusPill status={incident.status} />
                            </div>
                            <p className="mt-1 text-xs text-slate-500">
                              {incident.severity} ·{" "}
                              {new Date(incident.created_at).toLocaleTimeString()}
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
                    ))
                  : null}
              </div>
            </Panel>
          ) : null}

          {user === "admin@example.local" ||
          user === "auditor@example.local" ||
          user === "cto@example.local" ? (
            <Panel title="Approval History" icon={CheckCircle2}>
              <div className="grid gap-2">
                {approvalHistoryState === "loading" ? (
                  <p className="text-sm text-slate-500">Loading approval history...</p>
                ) : null}
                {approvalHistoryState === "error" ? (
                  <p className="text-sm text-coral">
                    Approval history could not be loaded. Check that the API is running for this
                    dashboard session.
                  </p>
                ) : null}
                {approvalHistoryState === "empty" ? (
                  <p className="text-sm text-slate-500">No approval history yet.</p>
                ) : null}
                {approvalHistoryState === "ready"
                  ? (approvalHistory.data ?? []).slice(0, 8).map((row) => (
                      <div
                        key={`${row.approval_step_id}-${row.decision_id ?? "pending"}`}
                        className="rounded-md border border-line p-3 text-sm"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="font-semibold">{row.project_name}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {row.step_type} · {row.assigned_role}
                            </p>
                          </div>
                          <StatusPill status={row.decision ?? row.step_status} />
                        </div>
                        <p className="mt-2 text-xs text-slate-600">
                          {row.actor_email ?? "Awaiting reviewer"}
                          {row.decided_at
                            ? ` · ${new Date(row.decided_at).toLocaleTimeString()}`
                            : ""}
                        </p>
                      </div>
                    ))
                  : null}
              </div>
            </Panel>
          ) : null}

          {user === "auditor@example.local" ? (
            <Panel title="Role Changes" icon={UserRound}>
              <div className="grid gap-2">
                {roleChangesState === "loading" ? (
                  <p className="text-sm text-slate-500">Loading role changes...</p>
                ) : null}
                {roleChangesState === "error" ? (
                  <p className="text-sm text-coral">
                    Role-change evidence could not be loaded. Check that the API is running for
                    this dashboard session.
                  </p>
                ) : null}
                {roleChangesState === "empty" ? (
                  <p className="text-sm text-slate-500">No role changes yet.</p>
                ) : null}
                {roleChangesState === "ready"
                  ? (roleChanges.data ?? []).slice(0, 6).map((change) => (
                      <div key={change.id} className="rounded-md border border-line p-3 text-sm">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-semibold">{change.target_email}</p>
                          <span className="text-xs text-slate-500">
                            {new Date(change.created_at).toLocaleTimeString()}
                          </span>
                        </div>
                        <p className="mt-1 text-slate-600">
                          {change.old_role} to {change.new_role} ·{" "}
                          {change.project_name ?? "organization"}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {change.source_event_type} · {change.actor_email ?? "system"}
                        </p>
                      </div>
                    ))
                  : null}
              </div>
            </Panel>
          ) : null}

          {user === "admin@example.local" ||
          user === "auditor@example.local" ||
          user === "cto@example.local" ? (
            <Panel title="Operational Health" icon={Activity}>
              {operationalHealthState === "loading" ? (
                <p className="text-sm text-slate-500">Loading operational telemetry...</p>
              ) : null}
              {operationalHealthState === "error" ? (
                <p className="text-sm text-coral">
                  Operational telemetry could not be loaded. Check that the API is running for this
                  dashboard session.
                </p>
              ) : null}
              {operationalHealthState === "empty" ? (
                <p className="text-sm text-slate-500">No operational telemetry yet.</p>
              ) : null}
              {operationalHealthState === "ready" && operationalHealth.data ? (
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <Detail
                    label="Requests"
                    value={operationalHealth.data.requests.requests_total.toString()}
                  />
                  <Detail
                    label="Avg latency"
                    value={`${operationalHealth.data.requests.average_duration_ms}ms`}
                  />
                  <Detail
                    label="Queued/failed"
                    value={operationalHealth.data.lifecycle_jobs.queued_or_failed.toString()}
                  />
                </div>
              ) : null}
            </Panel>
          ) : null}

          {user === "admin@example.local" ||
          user === "auditor@example.local" ||
          user === "cto@example.local" ? (
            <Panel title="Provisioning Evidence" icon={FileClock}>
              <div className="grid gap-2">
                {provisioningEvidenceState === "loading" ? (
                  <p className="text-sm text-slate-500">Loading provisioning evidence...</p>
                ) : null}
                {provisioningEvidenceState === "error" ? (
                  <p className="text-sm text-coral">
                    Provisioning evidence could not be loaded. Check that the API is running for
                    this dashboard session.
                  </p>
                ) : null}
                {provisioningEvidenceState === "empty" ? (
                  <p className="text-sm text-slate-500">No provisioning evidence yet.</p>
                ) : null}
                {provisioningEvidenceState === "ready"
                  ? (provisioningEvidence.data ?? []).slice(0, 5).map((evidence) => (
                      <div
                        key={evidence.assignment_id}
                        className="rounded-md border border-line p-3 text-sm"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="font-semibold">{evidence.project_name}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {evidence.provider.replaceAll("_", " ")} · provision{" "}
                              {evidence.provision_job_status ?? "pending"} · archive{" "}
                              {evidence.archive_job_status ?? "pending"}
                            </p>
                          </div>
                          <StatusPill status={evidence.evidence_result} />
                        </div>
                        <p className="mt-2 break-all text-xs text-slate-500">
                          {evidence.archive_checksum ?? evidence.external_resource_id}
                        </p>
                      </div>
                    ))
                  : null}
              </div>
            </Panel>
          ) : null}

          {user === "auditor@example.local" ? (
            <Panel title="Audit Trail" icon={Archive}>
              <div className="grid gap-2">
                <div className="grid gap-2 sm:grid-cols-2">
                  <TextInput
                    label="Event type filter"
                    placeholder="lifecycle.closed"
                    value={auditEventTypeFilter}
                    onChange={(event) => setAuditEventTypeFilter(event.target.value)}
                  />
                  <TextInput
                    label="Correlation filter"
                    placeholder="provider-webhook"
                    value={auditCorrelationFilter}
                    onChange={(event) => setAuditCorrelationFilter(event.target.value)}
                  />
                </div>
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
                {auditSummary.data ? (
                  <div className="grid gap-2 sm:grid-cols-3">
                    <div className="rounded-md border border-line p-3">
                      <p className="text-xs font-medium text-slate-500">Events</p>
                      <p className="mt-1 text-xl font-semibold text-ink">
                        {auditSummary.data.total_events}
                      </p>
                    </div>
                    <div className="rounded-md border border-line p-3">
                      <p className="text-xs font-medium text-slate-500">Correlations</p>
                      <p className="mt-1 text-xl font-semibold text-ink">
                        {auditSummary.data.unique_correlations}
                      </p>
                    </div>
                    <div className="rounded-md border border-line p-3">
                      <p className="text-xs font-medium text-slate-500">Success / review</p>
                      <p className="mt-1 text-xl font-semibold text-ink">
                        {auditSummary.data.success_events} / {auditSummary.data.failure_events}
                      </p>
                    </div>
                  </div>
                ) : null}
                {auditSummary.data?.by_event_type.length ? (
                  <div className="rounded-md bg-panel p-3 text-xs text-slate-600">
                    <p className="font-semibold text-slate-700">Top event types</p>
                    <p className="mt-1">
                      {auditSummary.data.by_event_type
                        .map((item) => `${item.name} (${item.count})`)
                        .join(" · ")}
                    </p>
                  </div>
                ) : null}
                {auditTrailState === "loading" ? (
                  <p className="text-sm text-slate-500">Loading audit trail...</p>
                ) : null}
                {auditTrailState === "error" ? (
                  <p className="text-sm text-coral">
                    Audit trail could not be loaded. Check that the API is running for this
                    dashboard session.
                  </p>
                ) : null}
                {auditTrailState === "empty" ? (
                  <p className="text-sm text-slate-500">No audit events yet.</p>
                ) : null}
                {auditTrailState === "ready"
                  ? (auditEvents.data ?? []).slice(0, 8).map((event) => (
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
                        <p className="mt-1 text-xs text-slate-500">
                          Target: {event.target_type}
                          {event.target_id ? `/${event.target_id.slice(0, 8)}` : ""} ·
                          Correlation: {event.correlation_id}
                        </p>
                        {compactMetadata(event.metadata_json) ? (
                          <p className="mt-1 text-xs text-slate-600">
                            {compactMetadata(event.metadata_json)}
                          </p>
                        ) : null}
                      </div>
                    ))
                  : null}
              </div>
            </Panel>
          ) : null}

          {user === "cto@example.local" ? (
            <Panel title="Executive Report" icon={LineChart}>
              {executiveReportState === "loading" ? (
                <p className="text-sm text-slate-500">Loading executive report...</p>
              ) : null}
              {executiveReportState === "error" ? (
                <p className="text-sm text-coral">
                  Executive report could not be loaded. Check that the API is running for this
                  dashboard session.
                </p>
              ) : null}
              {executiveReportState === "empty" ? (
                <p className="text-sm text-slate-500">
                  Executive report will populate after activity.
                </p>
              ) : null}
              {executiveReportState === "ready" && executiveReport.data ? (
                <div className="grid gap-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm text-slate-600">Executive and cost evidence</p>
                    <div className="flex gap-2">
                      <button
                        className="h-10 rounded-md border border-line px-3 text-sm font-semibold"
                        onClick={() => costAllocationDeliveryMutation.mutate()}
                      >
                        Schedule
                      </button>
                      <button
                        className="h-10 rounded-md border border-line px-3 text-sm font-semibold"
                        onClick={() => executiveReportExportMutation.mutate()}
                      >
                        Export Report
                      </button>
                      <button
                        className="h-10 rounded-md border border-line px-3 text-sm font-semibold"
                        onClick={() => costAllocationExportMutation.mutate()}
                      >
                        Export CSV
                      </button>
                    </div>
                  </div>
                  {costAllocationExportMutation.data ? (
                    <p className="rounded-md bg-panel p-2 text-xs text-slate-600">
                      Allocation export ready ·{" "}
                      {costAllocationExportMutation.data.trim().split("\n").length - 1} rows
                    </p>
                  ) : null}
                  {executiveReportExportMutation.data ? (
                    <p className="rounded-md bg-panel p-2 text-xs text-slate-600">
                      Executive report export ready ·{" "}
                      {executiveReportExportMutation.data.trim().split("\n").length - 1} rows
                    </p>
                  ) : null}
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
                      <p className="text-sm font-semibold">Provider spend mix</p>
                      <div className="mt-3 h-56">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={executiveProviderChartData}>
                            <CartesianGrid stroke="#d8dee8" strokeDasharray="3 3" />
                            <XAxis dataKey="provider" tick={{ fontSize: 11 }} />
                            <YAxis tick={{ fontSize: 11 }} />
                            <Tooltip />
                            <Bar dataKey="spend" fill="#4267ac" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                    <div className="rounded-md border border-line p-3">
                      <p className="text-sm font-semibold">Cost center budget</p>
                      <div className="mt-3 h-56">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={executiveCostCenterChartData}>
                            <CartesianGrid stroke="#d8dee8" strokeDasharray="3 3" />
                            <XAxis dataKey="costCenter" tick={{ fontSize: 11 }} />
                            <YAxis tick={{ fontSize: 11 }} />
                            <Tooltip />
                            <Bar dataKey="spend" stackId="budget" fill="#1f8f75" />
                            <Bar
                              dataKey="remaining"
                              stackId="budget"
                              fill="#cfeee6"
                              radius={[4, 4, 0, 0]}
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
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
                  {costAllocationDeliveries.data && costAllocationDeliveries.data.length > 0 ? (
                    <div className="rounded-md border border-line p-3">
                      <p className="text-sm font-semibold">Scheduled deliveries</p>
                      <div className="mt-2 grid gap-2">
                        {costAllocationDeliveries.data.slice(0, 3).map((delivery) => (
                          <div
                            key={delivery.id}
                            className="flex items-center justify-between gap-3 text-sm"
                          >
                            <span>{delivery.frequency}</span>
                            <span className="font-semibold">
                              {delivery.status} · {delivery.row_count} rows
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </Panel>
          ) : null}

          {canReadPrivilegedEvidence ? (
            <Panel title="Adoption Report" icon={LineChart}>
              {adoptionReportState === "loading" ? (
                <p className="text-sm text-slate-500">Loading adoption report...</p>
              ) : null}
              {adoptionReportState === "error" ? (
                <p className="text-sm text-coral">
                  Adoption report could not be loaded. Check that the API is running for this
                  dashboard session.
                </p>
              ) : null}
              {adoptionReportState === "empty" ? (
                <p className="text-sm text-slate-500">
                  Adoption reporting will populate after governed access activity.
                </p>
              ) : null}
              {adoptionReportState === "ready" && adoptionReport.data ? (
                <div className="grid gap-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm text-slate-600">Usage adoption and project activity</p>
                    <button
                      className="h-10 rounded-md border border-line px-3 text-sm font-semibold"
                      onClick={() => adoptionReportExportMutation.mutate()}
                    >
                      Export Adoption
                    </button>
                  </div>
                  {adoptionReportExportMutation.data ? (
                    <p className="rounded-md bg-panel p-2 text-xs text-slate-600">
                      Adoption export ready ·{" "}
                      {adoptionReportExportMutation.data.trim().split("\n").length - 1} rows
                    </p>
                  ) : null}
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Detail
                      label="Users with requests"
                      value={`${adoptionReport.data.users_with_requests}/${adoptionReport.data.total_users}`}
                    />
                    <Detail
                      label="Projects with usage"
                      value={adoptionReport.data.projects_with_usage.toString()}
                    />
                    <Detail
                      label="Active assignments"
                      value={adoptionReport.data.active_assignments.toString()}
                    />
                    <Detail
                      label="Request events"
                      value={adoptionReport.data.total_request_events.toLocaleString()}
                    />
                  </div>
                  <div className="grid gap-3 lg:grid-cols-2">
                    <div className="rounded-md border border-line p-3">
                      <p className="text-sm font-semibold">Provider adoption</p>
                      <div className="mt-3 h-56">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={adoptionProviderChartData}>
                            <CartesianGrid stroke="#d8dee8" strokeDasharray="3 3" />
                            <XAxis dataKey="provider" tick={{ fontSize: 11 }} />
                            <YAxis tick={{ fontSize: 11 }} />
                            <Tooltip />
                            <Bar
                              dataKey="activeAssignments"
                              fill="#1f8f75"
                              radius={[4, 4, 0, 0]}
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                    <div className="rounded-md border border-line p-3">
                      <p className="text-sm font-semibold">Department adoption</p>
                      <div className="mt-2 grid gap-2">
                        {adoptionReport.data.adoption_by_department.map((department) => (
                          <div
                            key={department.name}
                            className="flex items-center justify-between gap-3 text-sm"
                          >
                            <span>{department.name}</span>
                            <span className="font-semibold">
                              {department.request_count} requests · $
                              {department.total_spend}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="rounded-md border border-line p-3">
                    <p className="text-sm font-semibold">Project activity</p>
                    <div className="mt-2 grid gap-2">
                      {adoptionReport.data.project_activity.slice(0, 5).map((project) => (
                        <div
                          key={project.project_id ?? project.project_name}
                          className="grid gap-1 rounded-md border border-line bg-panel p-2 text-sm md:grid-cols-[minmax(0,1fr)_auto]"
                        >
                          <div>
                            <p className="font-semibold">{project.project_name}</p>
                            <p className="text-xs text-slate-500">
                              {project.cost_center} · {project.member_count} members
                              {project.owner_email ? ` · ${project.owner_email}` : ""}
                            </p>
                          </div>
                          <p className="text-sm font-semibold">
                            {project.active_assignments} active ·{" "}
                            {project.total_tokens.toLocaleString()} tokens
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
            </Panel>
          ) : null}

          {user === "cto@example.local" || user === "admin@example.local" ? (
            <Panel title="Extension Queue" icon={Clock3}>
              <div className="grid gap-2">
                {extensionQueueState === "loading" ? (
                  <p className="text-sm text-slate-500">Loading extension requests...</p>
                ) : null}
                {extensionQueueState === "error" ? (
                  <p className="text-sm text-coral">
                    Extension requests could not be loaded. Check that the API is running for this
                    dashboard session.
                  </p>
                ) : null}
                {extensionQueueState === "empty" ? (
                  <p className="text-sm text-slate-500">No extension requests.</p>
                ) : null}
                {extensionQueueState === "ready"
                  ? (extensions.data ?? []).map((extension) => (
                      <div key={extension.id} className="rounded-md border border-line p-3 text-sm">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="font-semibold">{extension.status}</p>
                            <p className="break-all text-xs text-slate-500">
                              {extension.request_id}
                            </p>
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
                    ))
                  : null}
              </div>
            </Panel>
          ) : null}
        </section>

        <aside className="grid content-start gap-5">
          <Panel title="Notifications" icon={Bell}>
            <div className="grid gap-2">
              {notificationsState === "ready" && unreadNotifications > 0 ? (
                <div className="flex justify-end">
                  <button
                    className="rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink transition hover:bg-panel"
                    disabled={readAllNotificationsMutation.isPending}
                    onClick={() => readAllNotificationsMutation.mutate()}
                  >
                    Mark all read
                  </button>
                </div>
              ) : null}
              {notificationsState === "loading" ? (
                <p className="text-sm text-slate-500">Loading notifications...</p>
              ) : null}
              {notificationsState === "error" ? (
                <p className="text-sm text-coral">
                  Notifications could not be loaded. Check that the API is running for this
                  dashboard session.
                </p>
              ) : null}
              {notificationsState === "empty" ? (
                <p className="text-sm text-slate-500">No notifications for this identity.</p>
              ) : null}
              {notificationsState === "ready"
                ? (notifications.data ?? []).slice(0, 6).map((notification) => (
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
                        <div className="flex flex-wrap items-center justify-end gap-2 text-xs text-slate-500">
                          <span>{notification.delivery_status}</span>
                          <span>{new Date(notification.created_at).toLocaleTimeString()}</span>
                        </div>
                      </div>
                      <p className="mt-1 text-slate-600">{notification.message}</p>
                    </button>
                  ))
                : null}
            </div>
          </Panel>

          <Panel title="New Request" icon={CloudCog}>
            <form
              className="grid gap-3"
              onSubmit={form.handleSubmit((values) => createMutation.mutate(values))}
            >
              <TextInput label="Project name" {...form.register("project_name")} />
              <TextArea label="Business justification" {...form.register("business_justification")} />
              <div className="grid gap-3 sm:grid-cols-2">
                <TextInput label="Sponsor" {...form.register("project_sponsor")} />
                <TextInput label="Cost center" {...form.register("cost_center")} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <TextInput label="Budget" type="number" {...form.register("requested_budget")} />
                <TextInput label="Users" type="number" {...form.register("expected_users")} />
              </div>
              <label className="grid gap-1 text-sm font-medium">
                Data class
                <select
                  className="h-10 min-w-0 rounded-md border border-line px-3"
                  {...form.register("data_classification")}
                >
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

          {canReviewApprovals ? (
            <Panel title="Approval Queue" icon={CheckCircle2}>
              <div className="grid gap-3">
                {approvalQueueState === "loading" ? (
                  <p className="text-sm text-slate-500">Loading approval queue...</p>
                ) : null}
                {approvalQueueState === "error" ? (
                  <p className="text-sm text-coral">
                    Approval queue is unavailable for this reviewer session.
                  </p>
                ) : null}
                {approvalQueueState === "empty" ? (
                  <p className="text-sm text-slate-500">No pending approvals.</p>
                ) : null}
                {approvalQueueState === "ready"
                  ? (approvals.data ?? []).map((step) => {
                      const approvalRequest = requestById.get(step.request_id);
                      return (
                        <div key={step.step_id} className="rounded-md border border-line p-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold capitalize">
                                {step.step_type.replaceAll("_", " ")}
                              </p>
                              <p className="mt-1 text-sm text-slate-600">
                                {step.project_name}
                              </p>
                              <p className="mt-1 text-xs font-medium text-slate-500">
                                Requested by {step.requester_display_name} · {step.requester_email}
                              </p>
                              {approvalRequest ? (
                                <p className="mt-1 text-xs text-slate-500">
                                  {approvalRequest.provider_names.join(", ")} ·{" "}
                                  {approvalRequest.currency} {approvalRequest.requested_budget} ·{" "}
                                  {approvalRequest.data_classification}
                                </p>
                              ) : null}
                            </div>
                            <div className="flex gap-2">
                              <button
                                data-testid={`approve-${step.step_type}`}
                                className="rounded-md bg-mint px-3 py-2 text-xs font-semibold text-white"
                                onClick={() =>
                                  approvalMutation.mutate({
                                    stepId: step.step_id,
                                    decision: "approve"
                                  })
                                }
                              >
                                Approve
                              </button>
                              <button
                                className="rounded-md border border-coral px-3 py-2 text-xs font-semibold text-coral"
                                onClick={() =>
                                  approvalMutation.mutate({
                                    stepId: step.step_id,
                                    decision: "reject"
                                  })
                                }
                              >
                                Reject
                              </button>
                              <button
                                className="rounded-md border border-line px-3 py-2 text-xs font-semibold"
                                onClick={() =>
                                  approvalMutation.mutate({
                                    stepId: step.step_id,
                                    decision: "request_information"
                                  })
                              }
                            >
                                Request Info
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })
                  : null}
              </div>
            </Panel>
          ) : null}
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

function AuthShell({
  title,
  detail,
  actionLabel,
  onAction
}: {
  title: string;
  detail: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <main className="grid min-h-screen place-items-center bg-panel px-5">
      <section className="w-full max-w-md rounded-md border border-line bg-white p-6 shadow-quiet">
        <ShieldCheck className="h-8 w-8 text-mint" aria-hidden />
        <h1 className="mt-4 text-2xl font-semibold text-ink">{title}</h1>
        <p className="mt-2 text-sm text-slate-600">{detail}</p>
        {actionLabel && onAction ? (
          <button
            type="button"
            className="mt-5 h-10 rounded-md bg-mint px-4 text-sm font-semibold text-white"
            onClick={onAction}
          >
            {actionLabel}
          </button>
        ) : null}
      </section>
    </main>
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
  <label className="grid min-w-0 gap-1 text-sm font-medium">
    {label}
    <input className="h-10 min-w-0 rounded-md border border-line px-3" {...props} />
  </label>
);

const TextArea = ({
  label,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) => (
  <label className="grid min-w-0 gap-1 text-sm font-medium">
    {label}
    <textarea className="min-h-20 min-w-0 rounded-md border border-line px-3 py-2" {...props} />
  </label>
);
