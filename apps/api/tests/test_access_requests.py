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

    evaluation = client.get(
        f"/access-requests/{created['id']}/policy-evaluation",
        headers={"x-dev-user": "employee@example.local"},
    )
    assert evaluation.status_code == 200
    assert evaluation.json()["approval_path"] == ["manager", "cto"]


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

    restored = client.post(
        "/developer/restore",
        headers={"x-dev-user": "admin@example.local"},
        json={"assignment_id": assignment_id, "reason": "Restore after demo threshold."},
    )
    assert restored.status_code == 200
    assert restored.json()["request_status"] == "ACTIVE"

    expired = client.post(
        "/developer/expire",
        headers={"x-dev-user": "admin@example.local"},
        json={"assignment_id": assignment_id, "reason": "Close demo project."},
    )
    assert expired.status_code == 200
    assert expired.json()["status"] == "deprovisioned"
    assert expired.json()["request_status"] == "CLOSED"

    archives = client.get("/developer/archives", headers={"x-dev-user": "admin@example.local"})
    assert archives.status_code == 200
    assert archives.json()[0]["storage_provider"] == "local"

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    event_types = {event["event_type"] for event in audit.json()}
    assert {
        "budget.warning",
        "budget.critical",
        "budget.enforcement",
        "lifecycle.closed",
    } <= event_types
