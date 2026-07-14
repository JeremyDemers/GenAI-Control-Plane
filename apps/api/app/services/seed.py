from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import RoleName
from app.models.entities import Role, User
from app.services.policies import ensure_standard_policy

DEMO_USERS: dict[str, tuple[str, RoleName]] = {
    "employee@example.local": ("Erin Employee", RoleName.EMPLOYEE),
    "owner@example.local": ("Omar Owner", RoleName.PROJECT_OWNER),
    "owner2@example.local": ("Olivia Owner", RoleName.PROJECT_OWNER),
    "approver@example.local": ("Avery Approver", RoleName.APPROVER),
    "security@example.local": ("Sam Security", RoleName.SECURITY_REVIEWER),
    "admin@example.local": ("Priya Platform", RoleName.PLATFORM_ADMIN),
    "auditor@example.local": ("Audra Auditor", RoleName.SECURITY_AUDITOR),
    "cto@example.local": ("Casey CTO", RoleName.CTO),
}


def seed_development_data(db: Session) -> None:
    roles_by_name: dict[str, Role] = {}
    for role_name in RoleName:
        role = db.scalar(select(Role).where(Role.name == role_name.value))
        if not role:
            role = Role(name=role_name.value, description=f"{role_name.value} application role")
            db.add(role)
            db.flush()
        roles_by_name[role.name] = role

    for email, (display_name, role_name) in DEMO_USERS.items():
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email, display_name=display_name)
            db.add(user)
            db.flush()
        role = roles_by_name[role_name.value]
        if role not in user.roles:
            user.roles.append(role)

    ensure_standard_policy(db)
    db.commit()
