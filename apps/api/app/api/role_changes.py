from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.core.database import get_db
from app.models.entities import AuditEvent, Project, User
from app.schemas import RoleChangeOut

router = APIRouter(prefix="/role-changes", tags=["role changes"])

ROLE_CHANGE_EVENTS = {"project.member_added", "project.reassigned"}


def actor_email(db: Session, event: AuditEvent) -> str | None:
    if event.actor_user_id is None:
        return None
    actor = db.get(User, event.actor_user_id)
    return actor.email if actor else None


def project_name(db: Session, project_id: str | None) -> str | None:
    if project_id is None:
        return None
    project = db.get(Project, project_id)
    return project.name if project else None


def role_changes_for_event(db: Session, event: AuditEvent) -> list[RoleChangeOut]:
    metadata = event.metadata_json or {}
    common = {
        "project_id": event.project_id,
        "project_name": project_name(db, event.project_id),
        "actor_email": actor_email(db, event),
        "source_event_type": event.event_type,
        "reason": event.reason,
        "created_at": event.created_at,
    }
    if event.event_type == "project.member_added":
        return [
            RoleChangeOut(
                id=f"{event.id}:member",
                target_email=str(metadata.get("email", "")),
                old_role="none",
                new_role=str(metadata.get("member_role", "member")),
                **common,
            )
        ]
    if event.event_type == "project.reassigned":
        return [
            RoleChangeOut(
                id=f"{event.id}:current-owner",
                target_email=str(metadata.get("current_owner_email", "")),
                old_role=str(metadata.get("current_owner_old_role", "owner")),
                new_role=str(metadata.get("current_owner_new_role", "collaborator")),
                **common,
            ),
            RoleChangeOut(
                id=f"{event.id}:proposed-owner",
                target_email=str(metadata.get("proposed_owner_email", "")),
                old_role=str(metadata.get("proposed_owner_old_role", "none")),
                new_role=str(metadata.get("proposed_owner_new_role", "owner")),
                **common,
            ),
        ]
    return []


@router.get("", response_model=list[RoleChangeOut])
def list_role_changes(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("roles:read_changes")),
) -> list[RoleChangeOut]:
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.event_type.in_(ROLE_CHANGE_EVENTS))
        .order_by(AuditEvent.created_at.desc())
        .limit(200)
    ).all()
    changes: list[RoleChangeOut] = []
    for event in events:
        changes.extend(role_changes_for_event(db, event))
    return changes
