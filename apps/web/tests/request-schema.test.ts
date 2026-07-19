import { describe, expect, it } from "vitest";

import {
  accessRequestSchema,
  providerDescription,
  providerLabel,
  providerOptions
} from "@/lib/request-schema";

describe("accessRequestSchema", () => {
  it("accepts the seeded interview demo request", () => {
    const start = new Date();
    const end = new Date();
    end.setDate(start.getDate() + 14);

    const parsed = accessRequestSchema.parse({
      project_name: "Interview Demo Sandbox",
      business_justification: "Evaluate governed AI assistance for support workflows.",
      project_sponsor: "Casey CTO",
      cost_center: "ENG-AI",
      requested_start_at: start.toISOString(),
      requested_end_at: end.toISOString(),
      requested_budget: 100,
      currency: "USD",
      requested_providers: ["amazon_bedrock", "github_copilot"],
      requested_services: ["claude-sonnet"],
      expected_users: 4,
      requested_collaborators: ["owner@example.local"],
      data_classification: "internal",
      uses_source_code: true,
      expected_artifacts: ["usage report"],
      expected_usage_pattern: "Two-week prototype validation.",
      estimated_monthly_volume: 200000
    });

    expect(parsed.requested_providers).toContain("github_copilot");
  });

  it("rejects empty provider selections", () => {
    const result = accessRequestSchema.safeParse({
      project_name: "Demo",
      business_justification: "Evaluate governed AI assistance for support workflows.",
      project_sponsor: "Casey CTO",
      cost_center: "ENG-AI",
      requested_start_at: new Date().toISOString(),
      requested_end_at: new Date(Date.now() + 86400000).toISOString(),
      requested_budget: 100,
      currency: "USD",
      requested_providers: [],
      expected_users: 4,
      data_classification: "internal",
      expected_usage_pattern: "Two-week prototype validation.",
      estimated_monthly_volume: 200000
    });

    expect(result.success).toBe(false);
  });

  it("uses current Google provider options and labels", () => {
    expect(providerOptions).toContain("google_gemini_enterprise_app");
    expect(providerOptions).toContain("google_gemini_enterprise_agent_platform");
    expect(providerOptions).not.toContain("google_gemini_enterprise");
    expect(providerOptions).not.toContain("google_vertex_ai");
    expect(providerLabel("google_gemini_enterprise_app")).toBe("Gemini Enterprise app");
    expect(providerLabel("google_gemini_enterprise_agent_platform")).toBe(
      "Gemini Enterprise Agent Platform"
    );
    expect(providerLabel("google_vertex_ai")).toBe("Gemini Enterprise Agent Platform");
    expect(providerDescription("google_gemini_enterprise_app")).toContain(
      "Employee-facing enterprise search"
    );
    expect(providerDescription("google_gemini_enterprise_agent_platform")).toContain(
      "Developer platform"
    );
  });
});
