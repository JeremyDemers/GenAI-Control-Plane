from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


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
