from collections.abc import Callable
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import has_permission
from app.models.entities import User
from app.services.audit import record_audit_event


def get_correlation_id(
    request: Request, x_correlation_id: str | None = Header(default=None)
) -> str:
    return str(
        getattr(request.state, "correlation_id", None)
        or x_correlation_id
        or str(uuid4())
    )


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    x_dev_user: str | None = Header(default=None),
) -> User:
    email = x_dev_user or "employee@example.local"
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Unknown development identity."},
        )
    request.state.user = user
    return user


def require_permission(permission: str) -> Callable[..., User]:
    def dependency(
        request: Request,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
        correlation_id: str = Depends(get_correlation_id),
    ) -> User:
        role_names = {role.name for role in user.roles}
        if has_permission(role_names, permission):
            return user

        record_audit_event(
            db,
            event_type="authorization.failure",
            actor_user_id=user.id,
            target_type="permission",
            target_id=permission,
            action="authorize",
            result="denied",
            reason=f"Missing permission {permission}",
            correlation_id=correlation_id,
            metadata_json={"roles": sorted(role_names), "path": request.url.path},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "You are not authorized to perform this action.",
                "correlation_id": correlation_id,
            },
        )

    return dependency
