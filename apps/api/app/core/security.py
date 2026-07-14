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
        "dashboard:employee",
    },
    RoleName.PROJECT_OWNER: {
        "projects:read_owned",
        "projects:members",
        "requests:create",
        "requests:read_project",
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
        "jobs:retry",
        "assignments:manage",
        "policies:manage",
    },
    RoleName.SECURITY_AUDITOR: {
        "audit:read_all",
        "audit:export",
        "requests:read_all",
        "policy_evaluations:read",
    },
    RoleName.CTO: {
        "approvals:review",
        "approvals:cto",
        "reports:executive",
        "projects:suspend",
        "requests:read_all",
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
