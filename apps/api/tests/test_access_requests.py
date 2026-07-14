from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.providers.base import ProviderOperationError


def request_payload() -> dict[str, object]:
    start_at = datetime.now(UTC) + timedelta(days=1)
    end_at = start_at + timedelta(days=14)
    return {
        "project_name": "Interview Demo Sandbox",
        "business_justification": "Evaluate governed AI assistance for customer support workflows.",
        "project_sponsor": "Casey CTO",
        "cost_center": "ENG-AI",
        "requested_start_at": start_at.isoformat(),
        "requested_end_at": end_at.isoformat(),
        "requested_budget": "100",
        "currency": "USD",
        "requested_providers": ["amazon_bedrock", "github_copilot"],
        "requested_services": ["claude-sonnet", "copilot-business"],
        "expected_users": 4,
        "requested_collaborators": ["owner@example.local"],
        "data_classification": "internal",
        "uses_pii": False,
        "uses_confidential_data": False,
        "uses_regulated_data": False,
        "uses_source_code": True,
        "expected_artifacts": ["prompt templates", "usage report"],
        "expected_usage_pattern": "Burst testing during a two-week prototype.",
        "estimated_monthly_volume": 200000,
        "additional_notes": "Seeded for the portfolio demo.",
    }


def test_employee_can_submit_request_and_policy_records_cto_path(client: TestClient) -> None:
    response = client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=request_payload(),
    )
    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "AWAITING_MANAGER_APPROVAL"
    assert created["project_id"] is not None

    owner_projects = client.get("/projects", headers={"x-dev-user": "owner@example.local"})
    assert owner_projects.status_code == 200
    assert owner_projects.json()[0]["id"] == created["project_id"]
    assert owner_projects.json()[0]["member_count"] == 2

    project_members = client.get(
        f"/projects/{created['project_id']}/members",
        headers={"x-dev-user": "owner@example.local"},
    )
    assert project_members.status_code == 200
    assert {member["email"] for member in project_members.json()} == {
        "employee@example.local",
        "owner@example.local",
    }

    owner_requests = client.get(
        "/access-requests", headers={"x-dev-user": "owner@example.local"}
    )
    assert owner_requests.status_code == 200
    assert owner_requests.json()[0]["id"] == created["id"]

    evaluation = client.get(
        f"/access-requests/{created['id']}/policy-evaluation",
        headers={"x-dev-user": "employee@example.local"},
    )
    assert evaluation.status_code == 200
    assert evaluation.json()["approval_path"] == ["manager", "cto"]

    employee_notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    )
    assert employee_notifications.status_code == 200
    assert {
        notification["event_type"] for notification in employee_notifications.json()
    } >= {"request_submitted"}

    approver_notifications = client.get(
        "/notifications", headers={"x-dev-user": "approver@example.local"}
    )
    assert approver_notifications.status_code == 200
    assert {
        notification["event_type"] for notification in approver_notifications.json()
    } >= {"approval_required"}

    notification_id = employee_notifications.json()[0]["id"]
    read_response = client.post(
        f"/notifications/{notification_id}/read",
        headers={"x-dev-user": "employee@example.local"},
    )
    assert read_response.status_code == 200
    assert read_response.json()["read_at"] is not None

    denied_read = client.post(
        f"/notifications/{notification_id}/read",
        headers={"x-dev-user": "approver@example.local"},
    )
    assert denied_read.status_code == 404


def test_project_owner_can_add_existing_user_to_project(client: TestClient) -> None:
    created = client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=request_payload(),
    ).json()

    added = client.post(
        f"/projects/{created['project_id']}/members",
        headers={"x-dev-user": "owner@example.local", "x-correlation-id": "member-add"},
        json={"email": "security@example.local", "member_role": "collaborator"},
    )
    assert added.status_code == 201
    assert added.json()["email"] == "security@example.local"
    assert added.json()["member_role"] == "collaborator"

    duplicate = client.post(
        f"/projects/{created['project_id']}/members",
        headers={"x-dev-user": "owner@example.local"},
        json={"email": "security@example.local", "member_role": "collaborator"},
    )
    assert duplicate.status_code == 409

    members = client.get(
        f"/projects/{created['project_id']}/members",
        headers={"x-dev-user": "owner@example.local"},
    )
    assert {member["email"] for member in members.json()} == {
        "employee@example.local",
        "owner@example.local",
        "security@example.local",
    }

    security_requests = client.get(
        "/access-requests", headers={"x-dev-user": "security@example.local"}
    )
    assert security_requests.status_code == 200
    assert security_requests.json()[0]["id"] == created["id"]

    security_notifications = client.get(
        "/notifications", headers={"x-dev-user": "security@example.local"}
    )
    assert {notification["event_type"] for notification in security_notifications.json()} >= {
        "project_member_added"
    }

    denied = client.post(
        f"/projects/{created['project_id']}/members",
        headers={"x-dev-user": "employee@example.local"},
        json={"email": "cto@example.local", "member_role": "collaborator"},
    )
    assert denied.status_code == 403

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    event_types = {event["event_type"] for event in audit.json()}
    assert {"project.member_added", "authorization.failure"} <= event_types

    project_audit = client.get(
        f"/projects/{created['project_id']}/audit-events",
        headers={"x-dev-user": "owner@example.local"},
    )
    assert project_audit.status_code == 200
    assert "project.member_added" in {event["event_type"] for event in project_audit.json()}
    assert all(event["project_id"] == created["project_id"] for event in project_audit.json())

    denied_project_audit = client.get(
        f"/projects/{created['project_id']}/audit-events",
        headers={"x-dev-user": "approver@example.local"},
    )
    assert denied_project_audit.status_code == 404


def test_project_owner_reassignment_requires_acceptance_and_approval(
    client: TestClient,
) -> None:
    created = client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=request_payload(),
    ).json()

    denied = client.post(
        "/reassignments",
        headers={"x-dev-user": "employee@example.local"},
        json={
            "project_id": created["project_id"],
            "proposed_owner_email": "owner2@example.local",
            "justification": "Move ownership to the backup project owner for continuity.",
        },
    )
    assert denied.status_code == 403

    requested = client.post(
        "/reassignments",
        headers={"x-dev-user": "owner@example.local", "x-correlation-id": "reassign"},
        json={
            "project_id": created["project_id"],
            "proposed_owner_email": "owner2@example.local",
            "justification": "Move ownership to the backup project owner for continuity.",
        },
    )
    assert requested.status_code == 201
    assert requested.json()["status"] == "pending_acceptance"
    reassignment_id = requested.json()["id"]

    owner2_reassignments = client.get(
        "/reassignments", headers={"x-dev-user": "owner2@example.local"}
    )
    assert owner2_reassignments.status_code == 200
    assert owner2_reassignments.json()[0]["id"] == reassignment_id

    accepted = client.post(
        f"/reassignments/{reassignment_id}/accept",
        headers={"x-dev-user": "owner2@example.local"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "pending_approval"

    admin_reassignments = client.get(
        "/reassignments", headers={"x-dev-user": "admin@example.local"}
    )
    assert admin_reassignments.status_code == 200
    assert admin_reassignments.json()[0]["id"] == reassignment_id

    approved = client.post(
        f"/reassignments/{reassignment_id}/decision",
        headers={"x-dev-user": "admin@example.local"},
        json={"decision": "approve", "comments": "Approved after owner acceptance."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    members = client.get(
        f"/projects/{created['project_id']}/members",
        headers={"x-dev-user": "admin@example.local"},
    ).json()
    member_roles = {member["email"]: member["member_role"] for member in members}
    assert member_roles["owner@example.local"] == "collaborator"
    assert member_roles["owner2@example.local"] == "owner"

    owner2_projects = client.get("/projects", headers={"x-dev-user": "owner2@example.local"})
    assert owner2_projects.status_code == 200
    assert owner2_projects.json()[0]["owner_user_id"] == approved.json()["proposed_owner_id"]

    owner_notifications = client.get(
        "/notifications", headers={"x-dev-user": "owner@example.local"}
    ).json()
    owner2_notifications = client.get(
        "/notifications", headers={"x-dev-user": "owner2@example.local"}
    ).json()
    admin_notifications = client.get(
        "/notifications", headers={"x-dev-user": "admin@example.local"}
    ).json()
    assert {notification["event_type"] for notification in owner_notifications} >= {
        "project_reassigned"
    }
    assert {notification["event_type"] for notification in owner2_notifications} >= {
        "reassignment_requested",
        "project_reassigned",
    }
    assert {notification["event_type"] for notification in admin_notifications} >= {
        "reassignment_approval_required"
    }

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    event_types = {event["event_type"] for event in audit.json()}
    assert {
        "project.reassignment_requested",
        "project.reassignment_accepted",
        "project.reassigned",
    } <= event_types

    role_changes = client.get("/role-changes", headers={"x-dev-user": "auditor@example.local"})
    assert role_changes.status_code == 200
    role_rows = {
        (row["target_email"], row["old_role"], row["new_role"])
        for row in role_changes.json()
    }
    assert ("owner@example.local", "owner", "collaborator") in role_rows
    assert ("owner2@example.local", "none", "owner") in role_rows

    denied_role_changes = client.get(
        "/role-changes", headers={"x-dev-user": "employee@example.local"}
    )
    assert denied_role_changes.status_code == 403


def test_admin_can_publish_policy_version_used_by_new_requests(client: TestClient) -> None:
    policies = client.get("/policies", headers={"x-dev-user": "admin@example.local"})
    assert policies.status_code == 200
    active_policy = next(policy for policy in policies.json() if policy["active"])
    document = active_policy["document"]
    document["approval_rules"]["require_security_review_for"] = [
        "internal",
        "confidential",
        "regulated",
    ]

    published = client.post(
        "/policies/standard-ai-sandbox/versions",
        headers={"x-dev-user": "admin@example.local"},
        json={
            "document": document,
            "description": "Default governed sandbox policy with internal security review.",
        },
    )
    assert published.status_code == 201
    assert published.json()["version"] == active_policy["version"] + 1
    assert published.json()["active"] is True

    denied = client.post(
        "/policies/standard-ai-sandbox/versions",
        headers={"x-dev-user": "employee@example.local"},
        json={"document": document},
    )
    assert denied.status_code == 403

    payload = request_payload()
    payload["requested_providers"] = ["amazon_bedrock"]
    created = client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=payload,
    ).json()
    evaluation = client.get(
        f"/access-requests/{created['id']}/policy-evaluation",
        headers={"x-dev-user": "employee@example.local"},
    ).json()
    assert evaluation["policy_version_id"] == published.json()["id"]
    assert evaluation["approval_path"] == ["manager", "security"]
    assert "security_review_required" in evaluation["triggered_rules"]

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    assert any(event["event_type"] == "policy.version_published" for event in audit.json())


def test_admin_can_update_artifact_retention_policy_used_by_archives(
    client: TestClient,
) -> None:
    retention = client.get("/policies/retention", headers={"x-dev-user": "auditor@example.local"})
    assert retention.status_code == 200
    assert retention.json()["artifact_retention_days"] == 365

    denied_update = client.post(
        "/policies/retention",
        headers={"x-dev-user": "auditor@example.local"},
        json={
            "artifact_retention_days": 30,
            "reason": "Auditors cannot update retention policy.",
        },
    )
    assert denied_update.status_code == 403

    updated = client.post(
        "/policies/retention",
        headers={"x-dev-user": "admin@example.local", "x-correlation-id": "retention"},
        json={
            "artifact_retention_days": 30,
            "reason": "Reduce demo artifact retention for regulated cleanup evidence.",
        },
    )
    assert updated.status_code == 201
    assert updated.json()["artifact_retention_days"] == 30
    assert updated.json()["version"] == retention.json()["version"] + 1

    provision_demo_request(client)
    assignments = client.get(
        "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
    ).json()
    expired = client.post(
        "/developer/expire",
        headers={"x-dev-user": "admin@example.local"},
        json={"assignment_id": assignments[0]["id"], "reason": "Verify retention policy."},
    )
    assert expired.status_code == 200

    archives = client.get("/developer/archives", headers={"x-dev-user": "admin@example.local"})
    retention_expires_at = datetime.fromisoformat(archives.json()[0]["retention_expires_at"])
    if retention_expires_at.tzinfo is None:
        retention_expires_at = retention_expires_at.replace(tzinfo=UTC)
    days_until_retention_expires = (retention_expires_at - datetime.now(UTC)).days
    assert 28 <= days_until_retention_expires <= 30

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    assert "policy.retention_updated" in {event["event_type"] for event in audit.json()}


def test_auditor_cannot_submit_request_and_failure_is_audited(client: TestClient) -> None:
    response = client.post(
        "/access-requests",
        headers={"x-dev-user": "auditor@example.local", "x-correlation-id": "test-denied"},
        json=request_payload(),
    )
    assert response.status_code == 403

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    assert audit.status_code == 200
    events = audit.json()
    assert any(event["event_type"] == "authorization.failure" for event in events)


def test_approval_workflow_provisions_mock_assignments(client: TestClient) -> None:
    created = client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=request_payload(),
    ).json()

    manager_steps = client.get(
        "/approvals/pending", headers={"x-dev-user": "approver@example.local"}
    ).json()
    assert len(manager_steps) == 1
    approver_requests = client.get(
        "/access-requests", headers={"x-dev-user": "approver@example.local"}
    )
    assert approver_requests.status_code == 200
    assert approver_requests.json()[0]["id"] == created["id"]
    manager_decision = client.post(
        f"/approvals/{manager_steps[0]['step_id']}",
        headers={"x-dev-user": "approver@example.local"},
        json={"decision": "approve", "comments": "Business case is clear."},
    )
    assert manager_decision.status_code == 200
    assert manager_decision.json()["status"] == "AWAITING_CTO_APPROVAL"
    cto_notifications = client.get(
        "/notifications", headers={"x-dev-user": "cto@example.local"}
    ).json()
    assert {notification["event_type"] for notification in cto_notifications} >= {
        "approval_required"
    }

    cto_steps = client.get("/approvals/pending", headers={"x-dev-user": "cto@example.local"}).json()
    assert len(cto_steps) == 1
    cto_decision = client.post(
        f"/approvals/{cto_steps[0]['step_id']}",
        headers={"x-dev-user": "cto@example.local"},
        json={"decision": "approve", "comments": "Approved for temporary demo access."},
    )
    assert cto_decision.status_code == 200
    assert cto_decision.json()["id"] == created["id"]
    assert cto_decision.json()["status"] == "ACTIVE"
    employee_notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    ).json()
    assert {notification["event_type"] for notification in employee_notifications} >= {
        "request_provisioned"
    }

    history = client.get("/approvals/history", headers={"x-dev-user": "auditor@example.local"})
    assert history.status_code == 200
    decisions = [row for row in history.json() if row["decision"] == "approve"]
    assert {row["actor_email"] for row in decisions} == {
        "approver@example.local",
        "cto@example.local",
    }
    assert {row["request_id"] for row in decisions} == {created["id"]}

    denied_history = client.get(
        "/approvals/history", headers={"x-dev-user": "employee@example.local"}
    )
    assert denied_history.status_code == 403


def test_cto_can_override_pending_approval_with_mandatory_justification(
    client: TestClient,
) -> None:
    created = client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=request_payload(),
    ).json()

    missing_justification = client.post(
        f"/approvals/override/{created['id']}",
        headers={"x-dev-user": "cto@example.local"},
        json={"decision": "approve", "justification": "Too short."},
    )
    assert missing_justification.status_code == 422

    denied = client.post(
        f"/approvals/override/{created['id']}",
        headers={"x-dev-user": "approver@example.local"},
        json={
            "decision": "approve",
            "justification": "Approvers cannot bypass the approval workflow.",
        },
    )
    assert denied.status_code == 403

    overridden = client.post(
        f"/approvals/override/{created['id']}",
        headers={"x-dev-user": "cto@example.local", "x-correlation-id": "cto-override"},
        json={
            "decision": "approve",
            "justification": "Urgent executive demo requires direct temporary approval.",
        },
    )
    assert overridden.status_code == 200
    assert overridden.json()["status"] == "ACTIVE"

    pending_after_override = client.get(
        "/approvals/pending", headers={"x-dev-user": "approver@example.local"}
    )
    assert pending_after_override.status_code == 200
    assert pending_after_override.json() == []

    assignments = client.get(
        "/provider-assignments", headers={"x-dev-user": "employee@example.local"}
    )
    assert assignments.status_code == 200
    assert len(assignments.json()) == 2

    history = client.get("/approvals/history", headers={"x-dev-user": "auditor@example.local"})
    assert history.status_code == 200
    override_rows = [row for row in history.json() if row["decision"] == "override_approve"]
    assert {row["actor_email"] for row in override_rows} == {"cto@example.local"}
    assert {row["request_id"] for row in override_rows} == {created["id"]}

    notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    ).json()
    assert {notification["event_type"] for notification in notifications} >= {
        "approval_overridden"
    }

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    assert "approval.override" in {event["event_type"] for event in audit.json()}


def test_approver_can_request_information_and_requester_can_respond(
    client: TestClient,
) -> None:
    created = client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=request_payload(),
    ).json()
    manager_step = client.get(
        "/approvals/pending", headers={"x-dev-user": "approver@example.local"}
    ).json()[0]

    information_request = client.post(
        f"/approvals/{manager_step['step_id']}",
        headers={"x-dev-user": "approver@example.local"},
        json={
            "decision": "request_information",
            "comments": "Clarify source-code retention controls.",
        },
    )
    assert information_request.status_code == 200
    assert information_request.json()["status"] == "SUBMITTED"

    pending_after_request = client.get(
        "/approvals/pending", headers={"x-dev-user": "approver@example.local"}
    )
    assert pending_after_request.status_code == 200
    assert pending_after_request.json() == []

    response = client.post(
        f"/access-requests/{created['id']}/information-response",
        headers={"x-dev-user": "employee@example.local"},
        json={
            "response": (
                "Artifacts are retained for seven days, then archived with checksum evidence."
            )
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "AWAITING_MANAGER_APPROVAL"

    pending_after_response = client.get(
        "/approvals/pending", headers={"x-dev-user": "approver@example.local"}
    )
    assert pending_after_response.status_code == 200
    assert pending_after_response.json()[0]["step_id"] == manager_step["step_id"]

    notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    ).json()
    assert {notification["event_type"] for notification in notifications} >= {
        "request_information_requested"
    }


def test_employee_can_cancel_own_pending_request(client: TestClient) -> None:
    created = client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=request_payload(),
    ).json()

    denied = client.post(
        f"/access-requests/{created['id']}/cancel",
        headers={"x-dev-user": "owner@example.local"},
    )
    assert denied.status_code == 403

    cancelled = client.post(
        f"/access-requests/{created['id']}/cancel",
        headers={"x-dev-user": "employee@example.local"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    manager_steps = client.get(
        "/approvals/pending", headers={"x-dev-user": "approver@example.local"}
    ).json()
    assert manager_steps == []

    notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    ).json()
    assert {notification["event_type"] for notification in notifications} >= {
        "request_cancelled"
    }


def provision_demo_request(client: TestClient) -> dict[str, object]:
    created = client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=request_payload(),
    ).json()
    manager_step = client.get(
        "/approvals/pending", headers={"x-dev-user": "approver@example.local"}
    ).json()[0]
    client.post(
        f"/approvals/{manager_step['step_id']}",
        headers={"x-dev-user": "approver@example.local"},
        json={"decision": "approve", "comments": "Approved."},
    )
    cto_step = client.get("/approvals/pending", headers={"x-dev-user": "cto@example.local"}).json()[
        0
    ]
    client.post(
        f"/approvals/{cto_step['step_id']}",
        headers={"x-dev-user": "cto@example.local"},
        json={"decision": "approve", "comments": "Approved."},
    )
    return created


def test_retryable_provider_failure_creates_safe_lifecycle_job(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingAdapter:
        def __init__(self, provider: str) -> None:
            self.name = provider

        async def provision_access(
            self, request_id: str, idempotency_key: str
        ) -> dict[str, object]:
            del request_id, idempotency_key
            raise ProviderOperationError(
                "Mock provider timeout",
                retryable=True,
                details={
                    "code": "timeout",
                    "message": "Provider API timed out.",
                    "operation": "provision_access",
                    "secret": "do-not-log",
                },
            )

    monkeypatch.setattr(
        "app.workers.jobs.get_provider_adapter",
        lambda provider: FailingAdapter(provider),
    )
    created = client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=request_payload(),
    ).json()
    manager_step = client.get(
        "/approvals/pending", headers={"x-dev-user": "approver@example.local"}
    ).json()[0]
    client.post(
        f"/approvals/{manager_step['step_id']}",
        headers={"x-dev-user": "approver@example.local"},
        json={"decision": "approve", "comments": "Approved."},
    )
    cto_step = client.get("/approvals/pending", headers={"x-dev-user": "cto@example.local"}).json()[
        0
    ]

    provision_failed = client.post(
        f"/approvals/{cto_step['step_id']}",
        headers={"x-dev-user": "cto@example.local", "x-correlation-id": "provider-failure"},
        json={"decision": "approve", "comments": "Approved."},
    )
    assert provision_failed.status_code == 200
    assert provision_failed.json()["status"] == "PROVISIONING_FAILED"

    jobs = client.get("/lifecycle-jobs", headers={"x-dev-user": "admin@example.local"})
    assert jobs.status_code == 200
    failed_job = jobs.json()[0]
    assert failed_job["status"] == "failed"
    assert failed_job["attempt_count"] == 1
    assert failed_job["failure_information"]["retryable"] is True
    assert failed_job["failure_information"]["details"]["code"] == "timeout"
    assert "secret" not in failed_job["failure_information"]["details"]

    denied_jobs = client.get("/lifecycle-jobs", headers={"x-dev-user": "employee@example.local"})
    assert denied_jobs.status_code == 403

    retried = client.post(
        f"/lifecycle-jobs/{failed_job['id']}/retry",
        headers={"x-dev-user": "admin@example.local", "x-correlation-id": "job-retry"},
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "queued"
    assert retried.json()["attempt_count"] == 2
    assert retried.json()["failure_information"] == {}

    notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    ).json()
    assert "provisioning_failed" in {
        notification["event_type"] for notification in notifications
    }
    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    event_types = {event["event_type"] for event in audit.json()}
    assert {"provider.provision_failed", "lifecycle_job.retry_requested"} <= event_types
    assert created["id"] == provision_failed.json()["id"]


def test_developer_lifecycle_demo_controls_create_evidence(client: TestClient) -> None:
    provision_demo_request(client)
    assignments = client.get(
        "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
    )
    assert assignments.status_code == 200
    assignment_id = assignments.json()[0]["id"]

    warning = client.post(
        "/developer/simulate-usage",
        headers={"x-dev-user": "admin@example.local"},
        json={
            "assignment_id": assignment_id,
            "tokens": 70000,
            "request_count": 140,
            "cost_amount": "70",
        },
    )
    assert warning.status_code == 200
    assert warning.json()["audit_event"] == "budget.warning"

    critical = client.post(
        "/developer/simulate-usage",
        headers={"x-dev-user": "admin@example.local"},
        json={
            "assignment_id": assignment_id,
            "tokens": 20000,
            "request_count": 40,
            "cost_amount": "20",
        },
    )
    assert critical.status_code == 200
    assert critical.json()["audit_event"] == "budget.critical"

    enforcement = client.post(
        "/developer/simulate-usage",
        headers={"x-dev-user": "admin@example.local"},
        json={
            "assignment_id": assignment_id,
            "tokens": 10000,
            "request_count": 20,
            "cost_amount": "10",
        },
    )
    assert enforcement.status_code == 200
    assert enforcement.json()["status"] == "suspended"
    assert enforcement.json()["request_status"] == "SUSPENDED"
    employee_notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    ).json()
    admin_notifications = client.get(
        "/notifications", headers={"x-dev-user": "admin@example.local"}
    ).json()
    assert {notification["event_type"] for notification in employee_notifications} >= {
        "budget_warning",
        "access_suspended",
    }
    assert {notification["event_type"] for notification in admin_notifications} >= {
        "budget_critical",
        "budget_enforcement",
    }
    incidents = client.get("/incidents", headers={"x-dev-user": "admin@example.local"})
    assert incidents.status_code == 200
    assert incidents.json()[0]["status"] == "open"
    assert incidents.json()[0]["severity"] == "high"

    auditor_incidents = client.get("/incidents", headers={"x-dev-user": "auditor@example.local"})
    assert auditor_incidents.status_code == 200
    assert auditor_incidents.json()[0]["id"] == incidents.json()[0]["id"]

    denied_incidents = client.get("/incidents", headers={"x-dev-user": "employee@example.local"})
    assert denied_incidents.status_code == 403

    denied_resolve = client.post(
        f"/incidents/{incidents.json()[0]['id']}/resolve",
        headers={"x-dev-user": "auditor@example.local"},
        json={"reason": "Auditors cannot resolve incidents."},
    )
    assert denied_resolve.status_code == 403

    resolved = client.post(
        f"/incidents/{incidents.json()[0]['id']}/resolve",
        headers={"x-dev-user": "admin@example.local"},
        json={"reason": "Budget enforcement reviewed and access restored."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    restored = client.post(
        "/developer/restore",
        headers={"x-dev-user": "admin@example.local"},
        json={"assignment_id": assignment_id, "reason": "Restore after demo threshold."},
    )
    assert restored.status_code == 200
    assert restored.json()["request_status"] == "ACTIVE"
    employee_notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    ).json()
    assert {notification["event_type"] for notification in employee_notifications} >= {
        "access_restored"
    }

    expired = client.post(
        "/developer/expire",
        headers={"x-dev-user": "admin@example.local"},
        json={"assignment_id": assignment_id, "reason": "Close demo project."},
    )
    assert expired.status_code == 200
    assert expired.json()["status"] == "deprovisioned"
    assert expired.json()["request_status"] == "CLOSED"
    employee_notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    ).json()
    admin_notifications = client.get(
        "/notifications", headers={"x-dev-user": "admin@example.local"}
    ).json()
    assert {notification["event_type"] for notification in employee_notifications} >= {
        "request_closed"
    }
    assert {notification["event_type"] for notification in admin_notifications} >= {
        "lifecycle_closed"
    }

    archives = client.get("/developer/archives", headers={"x-dev-user": "admin@example.local"})
    assert archives.status_code == 200
    assert archives.json()[0]["storage_provider"] == "local"

    jobs = client.get("/lifecycle-jobs", headers={"x-dev-user": "admin@example.local"})
    assert jobs.status_code == 200
    job_types = {job["job_type"] for job in jobs.json()}
    assert {"provision_access", "restore_access", "archive_and_deprovision"} <= job_types

    evidence = client.get(
        "/evidence/provisioning", headers={"x-dev-user": "auditor@example.local"}
    )
    assert evidence.status_code == 200
    evidence_row = next(
        row for row in evidence.json() if row["assignment_id"] == assignment_id
    )
    assert evidence_row["provision_job_status"] == "completed"
    assert evidence_row["archive_job_status"] == "completed"
    assert evidence_row["archive_checksum"] == archives.json()[0]["checksum"]
    assert evidence_row["evidence_result"] == "closed"

    denied_evidence = client.get(
        "/evidence/provisioning", headers={"x-dev-user": "employee@example.local"}
    )
    assert denied_evidence.status_code == 403

    denied_jobs = client.get("/lifecycle-jobs", headers={"x-dev-user": "employee@example.local"})
    assert denied_jobs.status_code == 403

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    event_types = {event["event_type"] for event in audit.json()}
    assert {
        "budget.warning",
        "budget.critical",
        "budget.enforcement",
        "incident.resolved",
        "lifecycle.closed",
    } <= event_types

    audit_export = client.get(
        "/audit-events/export", headers={"x-dev-user": "auditor@example.local"}
    )
    assert audit_export.status_code == 200
    assert audit_export.headers["content-type"].startswith("text/csv")
    assert "event_type" in audit_export.text.splitlines()[0]
    assert "lifecycle.closed" in audit_export.text

    denied_export = client.get(
        "/audit-events/export", headers={"x-dev-user": "employee@example.local"}
    )
    assert denied_export.status_code == 403


def test_usage_cost_budget_and_assignment_domain_endpoints(client: TestClient) -> None:
    provision_demo_request(client)
    assignments = client.get(
        "/provider-assignments", headers={"x-dev-user": "employee@example.local"}
    )
    assert assignments.status_code == 200
    assert len(assignments.json()) == 2
    assignment_id = assignments.json()[0]["id"]

    client.post(
        "/developer/simulate-usage",
        headers={"x-dev-user": "admin@example.local"},
        json={
            "assignment_id": assignment_id,
            "tokens": 1234,
            "request_count": 7,
            "cost_amount": "12.50",
        },
    )

    usage = client.get("/usage", headers={"x-dev-user": "employee@example.local"})
    assert usage.status_code == 200
    assert usage.json()[0]["tokens"] == 1234

    usage_for_assignment = client.get(
        f"/usage?assignment_id={assignment_id}",
        headers={"x-dev-user": "employee@example.local"},
    )
    assert usage_for_assignment.status_code == 200
    assert usage_for_assignment.json()[0]["assignment_id"] == assignment_id

    costs = client.get("/costs", headers={"x-dev-user": "employee@example.local"})
    assert costs.status_code == 200
    assert costs.json()[0]["amount"] == "12.50"
    assert costs.json()[0]["cost_type"] == "estimated"

    budgets = client.get("/budgets", headers={"x-dev-user": "employee@example.local"})
    assert budgets.status_code == 200
    assert budgets.json()[0]["total_spend"] == "12.50"
    assert budgets.json()[0]["remaining_budget"] == "87.50"
    assert budgets.json()[0]["utilization_percent"] == 12

    owner_assignments = client.get(
        "/provider-assignments", headers={"x-dev-user": "owner@example.local"}
    )
    assert owner_assignments.status_code == 200
    assert len(owner_assignments.json()) == 2

    owner_usage = client.get(
        f"/usage?assignment_id={assignment_id}",
        headers={"x-dev-user": "owner@example.local"},
    )
    assert owner_usage.status_code == 200
    assert owner_usage.json()[0]["assignment_id"] == assignment_id

    auditor_assignments = client.get(
        "/provider-assignments", headers={"x-dev-user": "auditor@example.local"}
    )
    assert auditor_assignments.status_code == 200
    assert len(auditor_assignments.json()) == 2


def test_cto_can_suspend_project_with_audit_and_notifications(client: TestClient) -> None:
    created = provision_demo_request(client)

    denied = client.post(
        f"/projects/{created['project_id']}/suspend",
        headers={"x-dev-user": "employee@example.local"},
        json={"reason": "Employees cannot suspend projects."},
    )
    assert denied.status_code == 403

    suspended = client.post(
        f"/projects/{created['project_id']}/suspend",
        headers={"x-dev-user": "cto@example.local", "x-correlation-id": "project-suspend"},
        json={"reason": "Executive risk review paused this project."},
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"

    requests = client.get(
        "/access-requests", headers={"x-dev-user": "employee@example.local"}
    ).json()
    assert requests[0]["status"] == "SUSPENDED"

    assignments = client.get(
        "/provider-assignments", headers={"x-dev-user": "employee@example.local"}
    )
    assert {assignment["status"] for assignment in assignments.json()} == {"suspended"}

    employee_notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    ).json()
    assert "project_suspended" in {
        notification["event_type"] for notification in employee_notifications
    }

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    assert "project.suspended" in {event["event_type"] for event in audit.json()}


def test_provider_health_and_configuration_visibility(client: TestClient) -> None:
    health = client.get("/providers/health", headers={"x-dev-user": "employee@example.local"})
    assert health.status_code == 200
    assert len(health.json()) == 7
    assert {check["status"] for check in health.json()} == {"healthy"}

    configuration = client.get(
        "/providers/configuration", headers={"x-dev-user": "admin@example.local"}
    )
    assert configuration.status_code == 200
    assert len(configuration.json()) == 7
    assert {check["mode"] for check in configuration.json()} == {"mock"}
    assert all(check["configured"] for check in configuration.json())

    denied_configuration = client.get(
        "/providers/configuration", headers={"x-dev-user": "employee@example.local"}
    )
    assert denied_configuration.status_code == 403

    credentials = client.get(
        "/providers/credentials", headers={"x-dev-user": "auditor@example.local"}
    )
    assert credentials.status_code == 200
    assert len(credentials.json()) == 7
    first_credential = credentials.json()[0]
    assert first_credential["credential_reference"].startswith("vault://mock/")
    assert "secret" not in first_credential

    denied_credentials = client.get(
        "/providers/credentials", headers={"x-dev-user": "employee@example.local"}
    )
    assert denied_credentials.status_code == 403

    denied_rotation = client.post(
        f"/providers/credentials/{first_credential['id']}/rotate",
        headers={"x-dev-user": "auditor@example.local"},
        json={"reason": "Auditor attempted credential rotation during evidence review."},
    )
    assert denied_rotation.status_code == 403

    rotated = client.post(
        f"/providers/credentials/{first_credential['id']}/rotate",
        headers={"x-dev-user": "admin@example.local", "x-correlation-id": "credential-rotate"},
        json={"reason": "Rotate provider credential reference for demo governance evidence."},
    )
    assert rotated.status_code == 200
    assert rotated.json()["credential_reference"].startswith(
        f"vault://mock/{first_credential['provider']}/rotated-"
    )
    assert rotated.json()["credential_reference"] != first_credential["credential_reference"]
    assert rotated.json()["rotation_due_at"] is not None

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    rotated_events = [
        event for event in audit.json() if event["event_type"] == "provider.credential_rotated"
    ]
    assert rotated_events[0]["correlation_id"] == "credential-rotate"


def test_cto_can_view_executive_report_with_spend_rollups(client: TestClient) -> None:
    provision_demo_request(client)
    assignments = client.get(
        "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
    ).json()
    assignment_id = assignments[0]["id"]

    client.post(
        "/developer/simulate-usage",
        headers={"x-dev-user": "admin@example.local"},
        json={
            "assignment_id": assignment_id,
            "tokens": 5000,
            "request_count": 10,
            "cost_amount": "25",
        },
    )

    report = client.get("/reports/executive", headers={"x-dev-user": "cto@example.local"})
    assert report.status_code == 200
    body = report.json()
    assert body["total_requests"] == 1
    assert body["active_projects"] == 1
    assert body["total_budget"] == "100.00"
    assert body["total_spend"] == "25.00"
    assert body["remaining_budget"] == "75.00"
    assert body["requests_by_status"]["ACTIVE"] == 1
    spending_providers = {
        provider["provider"]: provider
        for provider in body["spend_by_provider"]
        if provider["spend"] != "0"
    }
    assert list(spending_providers.values())[0]["spend"] == "25.00"
    assert list(spending_providers.values())[0]["tokens"] == 5000
    assert body["spend_by_cost_center"][0]["cost_center"] == "ENG-AI"

    denied_report = client.get(
        "/reports/executive", headers={"x-dev-user": "employee@example.local"}
    )
    assert denied_report.status_code == 403


def test_cost_allocation_export_rolls_up_assignment_spend_and_is_audited(
    client: TestClient,
) -> None:
    provision_demo_request(client)
    assignments = client.get(
        "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
    ).json()
    assignment_id = assignments[0]["id"]

    client.post(
        "/developer/simulate-usage",
        headers={"x-dev-user": "admin@example.local"},
        json={
            "assignment_id": assignment_id,
            "tokens": 5000,
            "request_count": 10,
            "cost_amount": "25",
        },
    )

    export = client.get(
        "/reports/cost-allocation/export",
        headers={"x-dev-user": "cto@example.local", "x-correlation-id": "cost-export"},
    )
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert "cost_center,project_name,request_id,assignment_id,provider" in export.text
    assert "ENG-AI" in export.text
    assert "25.00" in export.text
    assert "5000" in export.text

    auditor_export = client.get(
        "/reports/cost-allocation/export", headers={"x-dev-user": "auditor@example.local"}
    )
    assert auditor_export.status_code == 200

    denied_export = client.get(
        "/reports/cost-allocation/export", headers={"x-dev-user": "employee@example.local"}
    )
    assert denied_export.status_code == 403

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    assert "report.cost_allocation_exported" in {event["event_type"] for event in audit.json()}


def test_cto_can_schedule_cost_allocation_delivery(client: TestClient) -> None:
    provision_demo_request(client)

    delivery = client.post(
        "/reports/cost-allocation/deliveries",
        headers={"x-dev-user": "cto@example.local", "x-correlation-id": "schedule-report"},
        json={"frequency": "weekly", "recipients": ["finance@example.local"]},
    )
    assert delivery.status_code == 201
    assert delivery.json()["status"] == "completed"
    assert delivery.json()["frequency"] == "weekly"
    assert delivery.json()["recipients"] == ["finance@example.local"]
    assert delivery.json()["row_count"] == 2

    deliveries = client.get(
        "/reports/cost-allocation/deliveries",
        headers={"x-dev-user": "auditor@example.local"},
    )
    assert deliveries.status_code == 200
    assert deliveries.json()[0]["id"] == delivery.json()["id"]

    denied = client.post(
        "/reports/cost-allocation/deliveries",
        headers={"x-dev-user": "auditor@example.local"},
        json={"frequency": "weekly", "recipients": ["finance@example.local"]},
    )
    assert denied.status_code == 403

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    assert "report.cost_allocation_delivery_scheduled" in {
        event["event_type"] for event in audit.json()
    }


def test_employee_can_request_extension_and_cto_can_approve(client: TestClient) -> None:
    created = provision_demo_request(client)
    current_end = datetime.fromisoformat(str(created["requested_end_at"]))
    requested_end_at = current_end + timedelta(days=7)

    extension = client.post(
        "/extensions",
        headers={"x-dev-user": "employee@example.local"},
        json={
            "request_id": created["id"],
            "requested_end_at": requested_end_at.isoformat(),
            "justification": "Need one more week to finish stakeholder validation safely.",
        },
    )
    assert extension.status_code == 201
    assert extension.json()["status"] == "pending"

    duplicate = client.post(
        "/extensions",
        headers={"x-dev-user": "employee@example.local"},
        json={
            "request_id": created["id"],
            "requested_end_at": (requested_end_at + timedelta(days=1)).isoformat(),
            "justification": "Trying to create a second pending extension request.",
        },
    )
    assert duplicate.status_code == 409

    denied_decision = client.post(
        f"/extensions/{extension.json()['id']}/decision",
        headers={"x-dev-user": "employee@example.local"},
        json={"decision": "approve", "comments": "Nope."},
    )
    assert denied_decision.status_code == 403

    approved = client.post(
        f"/extensions/{extension.json()['id']}/decision",
        headers={"x-dev-user": "cto@example.local"},
        json={"decision": "approve", "comments": "Temporary extension approved."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    requests = client.get(
        "/access-requests", headers={"x-dev-user": "employee@example.local"}
    ).json()
    assert datetime.fromisoformat(requests[0]["requested_end_at"]) == requested_end_at

    assignments = client.get(
        "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
    ).json()
    assert datetime.fromisoformat(assignments[0]["expires_at"]) == requested_end_at

    notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    ).json()
    assert {notification["event_type"] for notification in notifications} >= {
        "extension_approved"
    }
