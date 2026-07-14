"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  CloudCog,
  FileClock,
  ShieldCheck,
  UserRound
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
  createAccessRequest,
  decideApproval,
  getMe,
  getPolicyEvaluation,
  listPendingApprovals,
  listRequests,
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
  const approvals = useQuery({
    queryKey: ["approvals", user],
    queryFn: () => listPendingApprovals(user),
    retry: false
  });
  const selectedRequest = useMemo(
    () => requests.data?.find((request) => request.id === selectedRequestId) ?? requests.data?.[0],
    [requests.data, selectedRequestId]
  );
  const evaluation = useQuery({
    queryKey: ["policy-evaluation", user, selectedRequest?.id],
    queryFn: () => getPolicyEvaluation(user, selectedRequest?.id ?? ""),
    enabled: Boolean(selectedRequest?.id)
  });

  const form = useForm<AccessRequestFormValues>({
    resolver: zodResolver(accessRequestSchema),
    defaultValues
  });

  const createMutation = useMutation({
    mutationFn: (values: AccessRequestFormValues) => createAccessRequest(user, values),
    onSuccess: (created) => {
      setSelectedRequestId(created.id);
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
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
    }
  });

  const activeRequests = requests.data?.filter((request) => request.status === "ACTIVE").length ?? 0;
  const pendingRequests =
    requests.data?.filter((request) => request.status.includes("AWAITING")).length ?? 0;

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
          <Metric icon={AlertTriangle} label="Budget incidents" value="1" tone="amber" />
          <Metric icon={CloudCog} label="Provider health" value="7/7" tone="mint" />
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

          <Panel title="Requests" icon={FileClock}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-slate-500">
                    <th className="py-2 pr-3 font-medium">Project</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                    <th className="py-2 pr-3 font-medium">Providers</th>
                    <th className="py-2 pr-3 font-medium">Budget</th>
                    <th className="py-2 pr-3 font-medium">Expires</th>
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
                    </tr>
                  ))}
                  {requests.data?.length === 0 ? (
                    <tr>
                      <td className="py-8 text-slate-500" colSpan={5}>
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
        </section>

        <aside className="grid content-start gap-5">
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
              <input type="hidden" {...form.register("requested_start_at")} />
              <input type="hidden" {...form.register("requested_end_at")} />
              <input type="hidden" {...form.register("currency")} />
              <button
                className="h-10 rounded-md bg-ink px-4 text-sm font-semibold text-white disabled:opacity-60"
                disabled={createMutation.isPending}
              >
                Submit Request
              </button>
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

function StatusPill({ status }: { status: AccessRequest["status"] }) {
  const className = status === "ACTIVE" ? "bg-mint/10 text-mint" : "bg-amber/10 text-amber";
  return (
    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${className}`}>
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

