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
