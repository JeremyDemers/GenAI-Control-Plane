PROVIDER_OPERATION_PROFILES: dict[str, dict[str, str]] = {
    "amazon_bedrock": {
        "resource_type": "aws_iam_identity_center_permission_set",
        "scope": "bedrock:InvokeModel,bedrock:InvokeModelWithResponseStream",
        "subject_type": "identity-center-group",
    },
    "amazon_sagemaker": {
        "resource_type": "aws_iam_role_policy_attachment",
        "scope": "sagemaker:InvokeEndpoint",
        "subject_type": "iam-role",
    },
    "google_gemini_enterprise_app": {
        "resource_type": "google_gemini_enterprise_app_assignment",
        "scope": "gemini-enterprise-user-access",
        "subject_type": "google-group",
        "billing_model": "seat_or_subscription_allocation",
        "access_model": "employee_app_assignment",
        "attribution_strategy": "principal_plus_app_assignment",
        "usage_reporting_model": "seat_status_and_activity_freshness",
        "cost_reporting_model": "internally_allocated_subscription_cost",
    },
    "google_gemini_enterprise_agent_platform": {
        "resource_type": "google_project_iam_binding",
        "scope": "roles/aiplatform.user",
        "subject_type": "google-group",
        "billing_model": "gcp_consumption_attribution",
        "access_model": "project_iam_assignment",
        "attribution_strategy": "principal_plus_gcp_project",
        "usage_reporting_model": "project_model_and_agent_activity",
        "cost_reporting_model": "estimated_provider_reported_or_reconciled_cost",
    },
    "microsoft_foundry": {
        "resource_type": "azure_role_assignment",
        "scope": "Azure AI Developer",
        "subject_type": "entra-group",
    },
    "azure_openai": {
        "resource_type": "azure_role_assignment",
        "scope": "Cognitive Services OpenAI User",
        "subject_type": "entra-group",
    },
    "github_copilot": {
        "resource_type": "github_copilot_seat_assignment",
        "scope": "copilot-business-seat",
        "subject_type": "github-team",
    },
}


def provider_operation_profile(provider: str) -> dict[str, str]:
    return PROVIDER_OPERATION_PROFILES.get(
        provider,
        {
            "resource_type": "provider_access_grant",
            "scope": "least-privilege-genai-access",
            "subject_type": "provider-group",
        },
    )
