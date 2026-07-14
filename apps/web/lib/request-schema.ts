import { z } from "zod";

export const providerOptions = [
  "amazon_bedrock",
  "amazon_sagemaker",
  "google_gemini_enterprise",
  "google_vertex_ai",
  "microsoft_foundry",
  "azure_openai",
  "github_copilot"
] as const;

export const accessRequestSchema = z
  .object({
    project_name: z.string().min(3).max(180),
    business_justification: z.string().min(20),
    project_sponsor: z.string().min(3).max(180),
    cost_center: z.string().min(2).max(80),
    requested_start_at: z.string().datetime(),
    requested_end_at: z.string().datetime(),
    requested_budget: z.coerce.number().positive().max(100000),
    currency: z.string().length(3).default("USD"),
    requested_providers: z.array(z.enum(providerOptions)).min(1),
    requested_services: z.array(z.string()).default([]),
    expected_users: z.coerce.number().int().min(1).max(500),
    requested_collaborators: z.array(z.string().email()).default([]),
    data_classification: z.enum(["public", "internal", "confidential", "regulated", "restricted"]),
    uses_pii: z.boolean().default(false),
    uses_confidential_data: z.boolean().default(false),
    uses_regulated_data: z.boolean().default(false),
    uses_source_code: z.boolean().default(false),
    expected_artifacts: z.array(z.string()).default([]),
    expected_usage_pattern: z.string().min(3).max(240),
    estimated_monthly_volume: z.coerce.number().int().min(1).max(100000000),
    additional_notes: z.string().default("")
  })
  .refine((value) => new Date(value.requested_end_at) > new Date(value.requested_start_at), {
    path: ["requested_end_at"],
    message: "Expiration must be after the start date"
  });

export type AccessRequestFormValues = z.infer<typeof accessRequestSchema>;

