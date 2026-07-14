from enum import StrEnum


class RoleName(StrEnum):
    EMPLOYEE = "employee"
    PROJECT_OWNER = "project_owner"
    APPROVER = "approver"
    SECURITY_REVIEWER = "security_reviewer"
    PLATFORM_ADMIN = "platform_admin"
    SECURITY_AUDITOR = "security_auditor"
    CTO = "cto"


ROLE_PERMISSIONS: dict[RoleName, set[str]] = {
    RoleName.EMPLOYEE: {
        "requests:create",
        "requests:read_own",
        "requests:cancel_own",
        "assignments:read_own",
        "usage:read_own",
        "costs:read_own",
        "budgets:read_own",
        "dashboard:employee",
    },
    RoleName.PROJECT_OWNER: {
        "projects:read_owned",
        "projects:members",
        "reassignments:create",
        "requests:create",
        "requests:read_project",
        "assignments:read_project",
        "usage:read_project",
        "costs:read_project",
        "budgets:read_project",
        "dashboard:project",
    },
    RoleName.APPROVER: {
        "approvals:review",
        "requests:read_assigned",
        "dashboard:approver",
    },
    RoleName.SECURITY_REVIEWER: {
        "approvals:review",
        "approvals:security",
        "policy_evaluations:read",
        "audit:read_security",
    },
    RoleName.PLATFORM_ADMIN: {
        "admin:*",
        "requests:read_all",
        "providers:manage",
        "providers:read",
        "jobs:retry",
        "assignments:manage",
        "assignments:read_all",
        "usage:read_all",
        "costs:read_all",
        "budgets:read_all",
        "evidence:read",
        "reports:cost_export",
        "reports:schedule",
        "extensions:approve",
        "incidents:manage",
        "incidents:read",
        "policy_evaluations:read",
        "policies:manage",
        "reassignments:approve",
        "reassignments:read_all",
        "roles:read_changes",
    },
    RoleName.SECURITY_AUDITOR: {
        "audit:read_all",
        "audit:export",
        "incidents:read",
        "requests:read_all",
        "policy_evaluations:read",
        "providers:read",
        "assignments:read_all",
        "usage:read_all",
        "costs:read_all",
        "budgets:read_all",
        "evidence:read",
        "reports:cost_export",
        "roles:read_changes",
    },
    RoleName.CTO: {
        "approvals:review",
        "approvals:cto",
        "extensions:approve",
        "incidents:read",
        "reports:executive",
        "projects:suspend",
        "reassignments:approve",
        "reassignments:read_all",
        "requests:read_all",
        "providers:read",
        "assignments:read_all",
        "usage:read_all",
        "costs:read_all",
        "budgets:read_all",
        "evidence:read",
        "reports:cost_export",
        "reports:schedule",
        "roles:read_changes",
    },
}


def has_permission(role_names: set[str], permission: str) -> bool:
    for role_name in role_names:
        role = RoleName(role_name)
        permissions = ROLE_PERMISSIONS[role]
        if permission in permissions or any(
            granted.endswith(":*") and permission.startswith(granted[:-1])
            for granted in permissions
        ):
            return True
    return False
