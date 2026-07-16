import asyncio
import csv
import json
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.api.webhooks import webhook_signature
from app.auth.oidc import (
    OIDCAuthenticationError,
    effective_oidc_audience,
    effective_oidc_issuer,
    effective_oidc_jwks_url,
    effective_oidc_token_endpoint,
)
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.entities import ArtifactArchive
from app.observability.middleware import rate_limiter
from app.providers.base import ProviderOperationError
from app.workers.scheduler import drain_once

OIDC_TEST_AUDIENCE = "api://genai-control-plane-test"
OIDC_TEST_ISSUER = "https://login.example.test/tenant/v2.0"
OIDC_TEST_SECRET = "local-oidc-test-secret-with-32-bytes-minimum"


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


def oidc_auth_header(
    email: str,
    *,
    audience: str = OIDC_TEST_AUDIENCE,
    issuer: str = OIDC_TEST_ISSUER,
    groups: list[str] | None = None,
) -> dict[str, str]:
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": issuer,
        "aud": audience,
        "email": email,
        "iat": now,
        "exp": now + 300,
    }
    if groups is not None:
        claims["groups"] = groups
    token = jwt.encode(
        claims,
        OIDC_TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def oidc_access_token(
    email: str,
    *,
    audience: str = OIDC_TEST_AUDIENCE,
    issuer: str = OIDC_TEST_ISSUER,
    groups: list[str] | None = None,
) -> str:
    return oidc_auth_header(email, audience=audience, issuer=issuer, groups=groups)[
        "Authorization"
    ].removeprefix("Bearer ")


def oidc_rs256_auth_header(
    email: str,
    private_key: rsa.RSAPrivateKey,
    *,
    key_id: str,
) -> dict[str, str]:
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": OIDC_TEST_ISSUER,
            "aud": OIDC_TEST_AUDIENCE,
            "email": email,
            "iat": now,
            "exp": now + 300,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": key_id},
    )
    return {"Authorization": f"Bearer {token}"}


def configure_oidc_auth_for_test() -> dict[str, object]:
    settings = get_settings()
    original = {
        "dev_auth_enabled": settings.dev_auth_enabled,
        "oidc_issuer": settings.oidc_issuer,
        "oidc_audience": settings.oidc_audience,
        "oidc_hs256_secret": settings.oidc_hs256_secret,
        "oidc_jwks_url": settings.oidc_jwks_url,
        "oidc_jwks_json": settings.oidc_jwks_json,
        "oidc_allowed_algorithms": list(settings.oidc_allowed_algorithms),
        "oidc_group_claims": list(settings.oidc_group_claims),
        "oidc_group_role_map_json": settings.oidc_group_role_map_json,
        "oidc_auto_provision_users": settings.oidc_auto_provision_users,
        "oidc_auto_provision_default_role": settings.oidc_auto_provision_default_role,
        "oidc_token_endpoint": settings.oidc_token_endpoint,
        "oidc_client_id": settings.oidc_client_id,
        "oidc_client_secret": settings.oidc_client_secret,
        "auth_session_cookie_name": settings.auth_session_cookie_name,
        "auth_session_cookie_secure": settings.auth_session_cookie_secure,
        "auth_session_ttl_hours": settings.auth_session_ttl_hours,
    }
    settings.dev_auth_enabled = False
    settings.oidc_issuer = OIDC_TEST_ISSUER
    settings.oidc_audience = OIDC_TEST_AUDIENCE
    settings.oidc_hs256_secret = OIDC_TEST_SECRET
    settings.oidc_jwks_url = ""
    settings.oidc_jwks_json = ""
    settings.oidc_allowed_algorithms = ["HS256"]
    settings.oidc_group_claims = ["groups", "roles"]
    settings.oidc_group_role_map_json = ""
    settings.oidc_auto_provision_users = False
    settings.oidc_auto_provision_default_role = "employee"
    settings.oidc_token_endpoint = "https://login.example.test/token"
    settings.oidc_client_id = "genai-control-plane-test"
    settings.oidc_client_secret = ""
    settings.auth_session_cookie_name = "genai_cp_session"
    settings.auth_session_cookie_secure = False
    settings.auth_session_ttl_hours = 12
    return original


def restore_auth_settings(original: dict[str, object]) -> None:
    settings = get_settings()
    settings.dev_auth_enabled = bool(original["dev_auth_enabled"])
    settings.oidc_issuer = str(original["oidc_issuer"])
    settings.oidc_audience = str(original["oidc_audience"])
    settings.oidc_hs256_secret = str(original["oidc_hs256_secret"])
    settings.oidc_jwks_url = str(original["oidc_jwks_url"])
    settings.oidc_jwks_json = str(original["oidc_jwks_json"])
    settings.oidc_allowed_algorithms = cast(list[str], original["oidc_allowed_algorithms"])
    settings.oidc_group_claims = cast(list[str], original["oidc_group_claims"])
    settings.oidc_group_role_map_json = str(original["oidc_group_role_map_json"])
    settings.oidc_auto_provision_users = bool(original["oidc_auto_provision_users"])
    settings.oidc_auto_provision_default_role = str(
        original["oidc_auto_provision_default_role"]
    )
    settings.oidc_token_endpoint = str(original["oidc_token_endpoint"])
    settings.oidc_client_id = str(original["oidc_client_id"])
    settings.oidc_client_secret = str(original["oidc_client_secret"])
    settings.auth_session_cookie_name = str(original["auth_session_cookie_name"])
    settings.auth_session_cookie_secure = bool(original["auth_session_cookie_secure"])
    settings.auth_session_ttl_hours = cast(int, original["auth_session_ttl_hours"])


def test_oidc_bearer_token_authenticates_seeded_user(client: TestClient) -> None:
    original = configure_oidc_auth_for_test()
    try:
        response = client.get("/auth/me", headers=oidc_auth_header("employee@example.local"))
    finally:
        restore_auth_settings(original)

    assert response.status_code == 200
    assert response.json()["email"] == "employee@example.local"
    assert "employee" in response.json()["roles"]


def test_microsoft_tenant_derives_oidc_endpoints() -> None:
    settings = get_settings()
    original = {
        "microsoft_tenant_id": settings.microsoft_tenant_id,
        "oidc_issuer": settings.oidc_issuer,
        "oidc_audience": settings.oidc_audience,
        "oidc_jwks_url": settings.oidc_jwks_url,
        "oidc_token_endpoint": settings.oidc_token_endpoint,
        "oidc_client_id": settings.oidc_client_id,
    }
    try:
        settings.microsoft_tenant_id = "00000000-0000-0000-0000-000000000000"
        settings.oidc_issuer = ""
        settings.oidc_audience = ""
        settings.oidc_jwks_url = ""
        settings.oidc_token_endpoint = ""
        settings.oidc_client_id = "api-client-id"

        assert (
            effective_oidc_issuer(settings)
            == "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0"
        )
        assert effective_oidc_audience(settings) == "api-client-id"
        assert effective_oidc_jwks_url(settings) == (
            "https://login.microsoftonline.com/"
            "00000000-0000-0000-0000-000000000000/discovery/v2.0/keys"
        )
        assert effective_oidc_token_endpoint(settings) == (
            "https://login.microsoftonline.com/"
            "00000000-0000-0000-0000-000000000000/oauth2/v2.0/token"
        )
    finally:
        settings.microsoft_tenant_id = str(original["microsoft_tenant_id"])
        settings.oidc_issuer = str(original["oidc_issuer"])
        settings.oidc_audience = str(original["oidc_audience"])
        settings.oidc_jwks_url = str(original["oidc_jwks_url"])
        settings.oidc_token_endpoint = str(original["oidc_token_endpoint"])
        settings.oidc_client_id = str(original["oidc_client_id"])


def test_oidc_static_jwks_authenticates_rs256_token(client: TestClient) -> None:
    key_id = "test-rs256-key"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = key_id

    original = configure_oidc_auth_for_test()
    settings = get_settings()
    settings.oidc_hs256_secret = ""
    settings.oidc_jwks_json = json.dumps({"keys": [public_jwk]})
    settings.oidc_allowed_algorithms = ["RS256"]
    try:
        response = client.get(
            "/auth/me",
            headers=oidc_rs256_auth_header(
                "employee@example.local",
                private_key,
                key_id=key_id,
            ),
        )
    finally:
        restore_auth_settings(original)

    assert response.status_code == 200
    assert response.json()["email"] == "employee@example.local"


def test_oidc_group_claims_sync_application_roles(client: TestClient) -> None:
    original = configure_oidc_auth_for_test()
    settings = get_settings()
    settings.oidc_group_role_map_json = json.dumps(
        {
            "entra-platform-admins": ["platform_admin"],
            "entra-auditors": ["security_auditor"],
        }
    )
    try:
        admin_headers = oidc_auth_header(
            "employee@example.local",
            groups=["entra-platform-admins"],
        )
        me = client.get("/auth/me", headers=admin_headers)
        jobs = client.get("/lifecycle-jobs", headers=admin_headers)

        auditor_headers = oidc_auth_header(
            "auditor@example.local",
            groups=["entra-auditors"],
        )
        audit = client.get("/audit-events", headers=auditor_headers)
    finally:
        restore_auth_settings(original)

    assert me.status_code == 200
    assert set(me.json()["roles"]) == {"platform_admin"}
    assert jobs.status_code == 200
    assert "identity.roles_synchronized" in {event["event_type"] for event in audit.json()}


def test_dev_identity_header_is_rejected_when_dev_auth_is_disabled(
    client: TestClient,
) -> None:
    original = configure_oidc_auth_for_test()
    try:
        response = client.get("/auth/me", headers={"x-dev-user": "employee@example.local"})
    finally:
        restore_auth_settings(original)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHENTICATED"


def test_oidc_bearer_token_rejects_wrong_audience(client: TestClient) -> None:
    original = configure_oidc_auth_for_test()
    try:
        response = client.get(
            "/auth/me",
            headers=oidc_auth_header("employee@example.local", audience="api://wrong"),
        )
    finally:
        restore_auth_settings(original)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHENTICATED"


def test_oidc_callback_refresh_and_logout_use_server_session(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = configure_oidc_auth_for_test()
    exchanged_forms = []

    async def fake_exchange_oidc_code(**kwargs: object) -> dict[str, object]:
        exchanged_forms.append(kwargs)
        return {
            "access_token": oidc_access_token("employee@example.local"),
            "refresh_token": "refresh-token-one",
            "expires_in": 300,
        }

    async def fake_refresh_oidc_access_token(**kwargs: object) -> dict[str, object]:
        exchanged_forms.append(kwargs)
        return {
            "access_token": oidc_access_token("employee@example.local"),
            "refresh_token": "refresh-token-two",
            "expires_in": 300,
        }

    monkeypatch.setattr("app.api.auth.exchange_oidc_code", fake_exchange_oidc_code)
    monkeypatch.setattr("app.api.auth.refresh_oidc_access_token", fake_refresh_oidc_access_token)
    try:
        callback = client.post(
            "/auth/oidc/callback",
            json={
                "code": "authorization-code",
                "code_verifier": "a" * 64,
                "redirect_uri": "http://localhost:3000",
            },
        )
        refresh = client.post("/auth/oidc/refresh")
        logout = client.post("/auth/logout")
        refresh_after_logout = client.post("/auth/oidc/refresh")
        audit = client.get("/audit-events", headers=oidc_auth_header("auditor@example.local"))
    finally:
        restore_auth_settings(original)

    assert callback.status_code == 200
    assert callback.json()["user"]["email"] == "employee@example.local"
    assert "refresh-token-one" not in callback.text
    assert "httponly" in callback.headers["set-cookie"].lower()
    assert refresh.status_code == 200
    assert refresh.json()["user"]["email"] == "employee@example.local"
    assert logout.status_code == 204
    assert refresh_after_logout.status_code == 401
    assert exchanged_forms[0]["code"] == "authorization-code"
    assert exchanged_forms[1]["refresh_token"] == "refresh-token-one"
    assert audit.status_code == 200
    assert {"auth.session_created", "auth.session_revoked"} <= {
        event["event_type"] for event in audit.json()
    }


def test_oidc_callback_can_auto_provision_microsoft_user(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = configure_oidc_auth_for_test()
    settings = get_settings()
    settings.oidc_auto_provision_users = True

    async def fake_exchange_oidc_code(**kwargs: object) -> dict[str, object]:
        del kwargs
        now = int(time.time())
        access_token = jwt.encode(
            {
                "iss": OIDC_TEST_ISSUER,
                "aud": OIDC_TEST_AUDIENCE,
                "email": "jeremy@example.local",
                "name": "Jeremy Azure",
                "iat": now,
                "exp": now + 300,
            },
            OIDC_TEST_SECRET,
            algorithm="HS256",
        )
        return {
            "access_token": access_token,
            "refresh_token": "refresh-token-new-user",
            "expires_in": 300,
        }

    monkeypatch.setattr("app.api.auth.exchange_oidc_code", fake_exchange_oidc_code)
    try:
        exchange = client.post(
            "/auth/oidc/callback",
            json={
                "code": "authorization-code",
                "code_verifier": "v" * 43,
                "redirect_uri": "http://localhost:3001",
            },
        )
        me = client.get(
            "/auth/me",
            headers=oidc_auth_header("jeremy@example.local"),
        )
    finally:
        restore_auth_settings(original)

    assert exchange.status_code == 200
    assert exchange.json()["user"]["email"] == "jeremy@example.local"
    assert exchange.json()["user"]["display_name"] == "Jeremy Azure"
    assert exchange.json()["user"]["roles"] == ["employee"]
    assert me.status_code == 200
    assert me.json()["email"] == "jeremy@example.local"


def test_oidc_callback_surfaces_provider_error_detail(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = configure_oidc_auth_for_test()

    async def fake_exchange_oidc_code(**kwargs: object) -> dict[str, object]:
        del kwargs
        raise OIDCAuthenticationError(
            "invalid_grant: AADSTS50011 The redirect URI does not match the registered URI."
        )

    monkeypatch.setattr("app.api.auth.exchange_oidc_code", fake_exchange_oidc_code)
    try:
        exchange = client.post(
            "/auth/oidc/callback",
            json={
                "code": "authorization-code",
                "code_verifier": "v" * 43,
                "redirect_uri": "http://localhost:3001",
            },
        )
    finally:
        restore_auth_settings(original)

    assert exchange.status_code == 401
    assert exchange.json()["detail"] == {
        "code": "UNAUTHENTICATED",
        "message": (
            "OIDC authorization code exchange failed: invalid_grant: AADSTS50011 "
            "The redirect URI does not match the registered URI."
        ),
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
    assert {notification["delivery_status"] for notification in employee_notifications.json()} == {
        "pending"
    }

    notification_id = employee_notifications.json()[0]["id"]
    read_response = client.post(
        f"/notifications/{notification_id}/read",
        headers={
            "x-dev-user": "employee@example.local",
            "x-correlation-id": "notification-read",
        },
    )
    assert read_response.status_code == 200
    assert read_response.json()["read_at"] is not None

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    read_event = next(
        event for event in audit.json() if event["event_type"] == "notification.read"
    )
    assert read_event["target_id"] == notification_id
    assert read_event["correlation_id"] == "notification-read"
    assert read_event["metadata_json"]["event_type"] == "request_submitted"
    assert read_event["metadata_json"]["delivery_status"] == "pending"

    filtered_audit = client.get(
        "/audit-events",
        headers={"x-dev-user": "auditor@example.local"},
        params={
            "event_type": "notification.read",
            "correlation_id": "notification-read",
            "limit": 1,
        },
    )
    assert filtered_audit.status_code == 200
    assert len(filtered_audit.json()) == 1
    assert filtered_audit.json()[0]["id"] == read_event["id"]

    filtered_export = client.get(
        "/audit-events/export",
        headers={
            "x-dev-user": "auditor@example.local",
            "x-correlation-id": "filtered-audit-export",
        },
        params={"event_type": "notification.read", "correlation_id": "notification-read"},
    )
    assert filtered_export.status_code == 200
    rows = list(csv.DictReader(filtered_export.text.splitlines()))
    assert {row["event_type"] for row in rows} == {"notification.read"}
    assert {row["correlation_id"] for row in rows} == {"notification-read"}

    filtered_summary = client.get(
        "/audit-events/summary",
        headers={"x-dev-user": "auditor@example.local"},
        params={"event_type": "notification.read", "correlation_id": "notification-read"},
    )
    assert filtered_summary.status_code == 200
    assert filtered_summary.json()["total_events"] == 1
    assert filtered_summary.json()["unique_correlations"] == 1
    assert filtered_summary.json()["success_events"] == 1
    assert filtered_summary.json()["failure_events"] == 0
    assert filtered_summary.json()["by_event_type"] == [
        {"name": "notification.read", "count": 1}
    ]

    denied_summary = client.get(
        "/audit-events/summary", headers={"x-dev-user": "employee@example.local"}
    )
    assert denied_summary.status_code == 403

    denied_read = client.post(
        f"/notifications/{notification_id}/read",
        headers={"x-dev-user": "approver@example.local"},
    )
    assert denied_read.status_code == 404


def test_employee_can_mark_all_own_notifications_read(client: TestClient) -> None:
    client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=request_payload(),
    )

    employee_notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    )
    assert employee_notifications.status_code == 200
    assert any(notification["read_at"] is None for notification in employee_notifications.json())

    approver_notifications = client.get(
        "/notifications", headers={"x-dev-user": "approver@example.local"}
    )
    assert approver_notifications.status_code == 200
    assert any(notification["read_at"] is None for notification in approver_notifications.json())

    read_all = client.post(
        "/notifications/read-all",
        headers={
            "x-dev-user": "employee@example.local",
            "x-correlation-id": "notifications-read-all",
        },
    )
    assert read_all.status_code == 200
    assert read_all.json()["marked_read"] == len(employee_notifications.json())

    updated_employee_notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    )
    assert all(
        notification["read_at"] is not None
        for notification in updated_employee_notifications.json()
    )

    updated_approver_notifications = client.get(
        "/notifications", headers={"x-dev-user": "approver@example.local"}
    )
    assert any(
        notification["read_at"] is None for notification in updated_approver_notifications.json()
    )

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    read_all_event = next(
        event for event in audit.json() if event["event_type"] == "notification.read_all"
    )
    assert read_all_event["actor_user_id"] == updated_employee_notifications.json()[0]["user_id"]
    assert read_all_event["target_id"] == updated_employee_notifications.json()[0]["user_id"]
    assert read_all_event["correlation_id"] == "notifications-read-all"
    assert read_all_event["metadata_json"]["marked_read"] == len(employee_notifications.json())
    assert "request_submitted" in read_all_event["metadata_json"]["event_types"]


def test_worker_delivers_pending_notifications(client: TestClient) -> None:
    client.post(
        "/access-requests",
        headers={"x-dev-user": "employee@example.local"},
        json=request_payload(),
    )
    pending = client.get("/notifications", headers={"x-dev-user": "employee@example.local"})
    assert pending.status_code == 200
    assert pending.json()[0]["delivery_status"] == "pending"
    assert pending.json()[0]["delivered_at"] is None

    processed = asyncio.run(drain_once(limit=25, include_notifications=True))
    assert processed >= 2

    delivered = client.get("/notifications", headers={"x-dev-user": "employee@example.local"})
    assert delivered.json()[0]["delivery_status"] == "delivered"
    assert delivered.json()[0]["delivery_attempts"] == 1
    assert delivered.json()[0]["delivered_at"] is not None

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    assert "notification.delivered" in {event["event_type"] for event in audit.json()}


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
    assert all("metadata_json" in event for event in project_audit.json())

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


def test_worker_enforces_expired_archive_retention(client: TestClient) -> None:
    settings = get_settings()
    original_inline_execution = settings.lifecycle_inline_execution
    provision_demo_request(client)
    try:
        assignments = client.get(
            "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
        ).json()
        expired = client.post(
            "/developer/expire",
            headers={"x-dev-user": "admin@example.local"},
            json={"assignment_id": assignments[0]["id"], "reason": "Create archive evidence."},
        )
        assert expired.status_code == 200

        with SessionLocal() as db:
            archive = db.query(ArtifactArchive).first()
            assert archive is not None
            archive.retention_expires_at = datetime.now(UTC) - timedelta(days=1)
            original_location = archive.storage_location
            db.commit()

        settings.lifecycle_inline_execution = False
        sweep = client.post(
            "/developer/archives/enforce-retention",
            headers={
                "x-dev-user": "admin@example.local",
                "x-correlation-id": "retention-sweep",
            },
        )
        assert sweep.status_code == 200
        assert sweep.json()["status"] == "queued"
        assert sweep.json()["job_type"] == "enforce_archive_retention"

        assert asyncio.run(drain_once(limit=10)) == 1

        archives = client.get("/developer/archives", headers={"x-dev-user": "admin@example.local"})
        assert archives.status_code == 200
        assert archives.json()[0]["storage_location"].startswith("purged://")
        assert archives.json()[0]["storage_location"] != original_location

        jobs = client.get("/lifecycle-jobs", headers={"x-dev-user": "admin@example.local"})
        retention_job = next(
            job for job in jobs.json() if job["job_type"] == "enforce_archive_retention"
        )
        assert retention_job["status"] == "completed"
        assert retention_job["payload"]["purged_count"] == 1

        audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
        assert "artifact.retention_purged" in {event["event_type"] for event in audit.json()}
    finally:
        settings.lifecycle_inline_execution = original_inline_execution


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


def test_worker_drains_queued_provisioning_jobs(client: TestClient) -> None:
    settings = get_settings()
    original_inline_execution = settings.lifecycle_inline_execution
    settings.lifecycle_inline_execution = False
    try:
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
        cto_step = client.get(
            "/approvals/pending", headers={"x-dev-user": "cto@example.local"}
        ).json()[0]

        queued = client.post(
            f"/approvals/{cto_step['step_id']}",
            headers={"x-dev-user": "cto@example.local", "x-correlation-id": "queued-worker"},
            json={"decision": "approve", "comments": "Approved."},
        )
        assert queued.status_code == 200
        assert queued.json()["status"] == "PROVISIONING"

        jobs = client.get("/lifecycle-jobs", headers={"x-dev-user": "admin@example.local"})
        assert jobs.status_code == 200
        queued_jobs = jobs.json()
        assert {job["status"] for job in queued_jobs} == {"queued"}
        assert {job["attempt_count"] for job in queued_jobs} == {0}
        assert {job["payload"]["request_id"] for job in queued_jobs} == {created["id"]}
        assert {job["payload"]["correlation_id"] for job in queued_jobs} == {"queued-worker"}

        processed = asyncio.run(drain_once(limit=10))
        assert processed == 2

        requests = client.get(
            "/access-requests", headers={"x-dev-user": "employee@example.local"}
        ).json()
        assert requests[0]["status"] == "ACTIVE"
        completed_jobs = client.get(
            "/lifecycle-jobs", headers={"x-dev-user": "admin@example.local"}
        ).json()
        assert {job["status"] for job in completed_jobs} == {"completed"}
        assert {job["attempt_count"] for job in completed_jobs} == {1}

        notifications = client.get(
            "/notifications", headers={"x-dev-user": "employee@example.local"}
        ).json()
        assert "provisioning_queued" in {
            notification["event_type"] for notification in notifications
        }
    finally:
        settings.lifecycle_inline_execution = original_inline_execution


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
    assert manager_step["project_name"] == "Interview Demo Sandbox"
    assert manager_step["requester_email"] == "employee@example.local"
    assert manager_step["requester_display_name"] == "Erin Employee"

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
    return cast(dict[str, object], created)


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
    failed_job = next(job for job in jobs.json() if job["status"] == "failed")
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

    active_assignments = client.get(
        "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
    ).json()
    expiration_scan = client.post(
        "/developer/assignments/expiration-warnings",
        headers={
            "x-dev-user": "admin@example.local",
            "x-correlation-id": "expiration-warning-scan",
        },
    )
    assert expiration_scan.status_code == 200
    assert expiration_scan.json()["status"] == "completed"
    assert expiration_scan.json()["payload"]["warned_count"] == len(active_assignments)
    assert set(expiration_scan.json()["payload"]["warned_assignment_ids"]) == {
        assignment["id"] for assignment in active_assignments
    }

    duplicate_scan = client.post(
        "/developer/assignments/expiration-warnings",
        headers={
            "x-dev-user": "admin@example.local",
            "x-correlation-id": "expiration-warning-repeat",
        },
    )
    assert duplicate_scan.status_code == 200
    assert duplicate_scan.json()["payload"]["warned_count"] == 0

    employee_notifications = client.get(
        "/notifications", headers={"x-dev-user": "employee@example.local"}
    ).json()
    admin_notifications = client.get(
        "/notifications", headers={"x-dev-user": "admin@example.local"}
    ).json()
    assert {notification["event_type"] for notification in employee_notifications} >= {
        "access_expiration_warning"
    }
    assert {notification["event_type"] for notification in admin_notifications} >= {
        "access_expiration_warning"
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
        "lifecycle.expiration_warning",
        "lifecycle.closed",
    } <= event_types

    audit_export = client.get(
        "/audit-events/export", headers={"x-dev-user": "auditor@example.local"}
    )
    assert audit_export.status_code == 200
    assert audit_export.headers["content-type"].startswith("text/csv")
    assert "event_type" in audit_export.text.splitlines()[0]
    assert "metadata_json" in audit_export.text.splitlines()[0]
    assert "lifecycle.closed" in audit_export.text
    rows = list(csv.DictReader(audit_export.text.splitlines()))
    closed_row = next(row for row in rows if row["event_type"] == "lifecycle.closed")
    assert isinstance(json.loads(closed_row["metadata_json"]), dict)

    denied_export = client.get(
        "/audit-events/export", headers={"x-dev-user": "employee@example.local"}
    )
    assert denied_export.status_code == 403


def test_worker_drains_queued_restore_and_archive_jobs(client: TestClient) -> None:
    settings = get_settings()
    original_inline_execution = settings.lifecycle_inline_execution
    provision_demo_request(client)
    try:
        settings.lifecycle_inline_execution = False
        assignments = client.get(
            "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
        ).json()
        assignment_id = assignments[0]["id"]

        client.post(
            "/developer/simulate-usage",
            headers={"x-dev-user": "admin@example.local"},
            json={
                "assignment_id": assignment_id,
                "tokens": 100000,
                "request_count": 200,
                "cost_amount": "100",
            },
        )
        assert asyncio.run(drain_once(limit=10)) == 1

        restore = client.post(
            "/developer/restore",
            headers={"x-dev-user": "admin@example.local", "x-correlation-id": "queued-restore"},
            json={"assignment_id": assignment_id, "reason": "Queue restore for worker."},
        )
        assert restore.status_code == 200
        assert restore.json()["audit_event"] == "lifecycle_job.queued"
        assert restore.json()["status"] == "suspended"

        jobs = client.get("/lifecycle-jobs", headers={"x-dev-user": "admin@example.local"}).json()
        restore_job = next(job for job in jobs if job["job_type"] == "restore_access")
        assert restore_job["status"] == "queued"
        assert restore_job["payload"]["correlation_id"] == "queued-restore"

        assert asyncio.run(drain_once(limit=10)) == 1
        restored_assignments = client.get(
            "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
        ).json()
        assert restored_assignments[0]["status"] == "active"

        expire = client.post(
            "/developer/expire",
            headers={"x-dev-user": "admin@example.local", "x-correlation-id": "queued-archive"},
            json={"assignment_id": assignment_id, "reason": "Queue archive for worker."},
        )
        assert expire.status_code == 200
        assert expire.json()["audit_event"] == "lifecycle_job.queued"
        assert expire.json()["status"] == "active"

        jobs = client.get("/lifecycle-jobs", headers={"x-dev-user": "admin@example.local"}).json()
        archive_job = next(job for job in jobs if job["job_type"] == "archive_and_deprovision")
        assert archive_job["status"] == "queued"
        assert archive_job["payload"]["correlation_id"] == "queued-archive"

        assert asyncio.run(drain_once(limit=10)) == 1
        closed_assignments = client.get(
            "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
        ).json()
        assert closed_assignments[0]["status"] == "deprovisioned"
        archives = client.get("/developer/archives", headers={"x-dev-user": "admin@example.local"})
        assert archives.status_code == 200
        assert archives.json()[0]["storage_provider"] == "local"

        completed_jobs = client.get(
            "/lifecycle-jobs", headers={"x-dev-user": "admin@example.local"}
        ).json()
        assert {
            job["job_type"]: job["status"]
            for job in completed_jobs
            if job["job_type"] in {"restore_access", "archive_and_deprovision"}
        } == {"restore_access": "completed", "archive_and_deprovision": "completed"}
    finally:
        settings.lifecycle_inline_execution = original_inline_execution


def test_worker_drains_queued_usage_and_budget_job(client: TestClient) -> None:
    settings = get_settings()
    original_inline_execution = settings.lifecycle_inline_execution
    provision_demo_request(client)
    try:
        settings.lifecycle_inline_execution = False
        assignments = client.get(
            "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
        ).json()
        assignment_id = assignments[0]["id"]

        queued = client.post(
            "/developer/simulate-usage",
            headers={"x-dev-user": "admin@example.local", "x-correlation-id": "queued-usage"},
            json={
                "assignment_id": assignment_id,
                "tokens": 100000,
                "request_count": 200,
                "cost_amount": "100",
            },
        )
        assert queued.status_code == 200
        assert queued.json()["audit_event"] == "lifecycle_job.queued"
        assert queued.json()["status"] == "active"

        budgets_before = client.get("/budgets", headers={"x-dev-user": "admin@example.local"})
        assert budgets_before.status_code == 200
        assert Decimal(str(budgets_before.json()[0]["total_spend"])) == Decimal("0")

        jobs = client.get("/lifecycle-jobs", headers={"x-dev-user": "admin@example.local"}).json()
        usage_job = next(job for job in jobs if job["job_type"] == "record_usage_and_cost")
        assert usage_job["status"] == "queued"
        assert usage_job["payload"]["correlation_id"] == "queued-usage"

        assert asyncio.run(drain_once(limit=10)) == 1
        assignments_after = client.get(
            "/developer/assignments", headers={"x-dev-user": "admin@example.local"}
        ).json()
        assert assignments_after[0]["status"] == "suspended"
        budgets_after = client.get("/budgets", headers={"x-dev-user": "admin@example.local"})
        assert budgets_after.json()[0]["total_spend"] == "100.00"

        completed_jobs = client.get(
            "/lifecycle-jobs", headers={"x-dev-user": "admin@example.local"}
        ).json()
        completed_usage_job = next(
            job for job in completed_jobs if job["job_type"] == "record_usage_and_cost"
        )
        assert completed_usage_job["status"] == "completed"
        assert completed_usage_job["payload"]["audit_event"] == "budget.enforcement"
    finally:
        settings.lifecycle_inline_execution = original_inline_execution


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


def test_live_provider_mode_reports_safe_configuration_boundaries(client: TestClient) -> None:
    settings = get_settings()
    original_values = {
        "provider_mode": settings.provider_mode,
        "provider_live_operations_enabled": settings.provider_live_operations_enabled,
        "aws_region": settings.aws_region,
        "azure_tenant_id": settings.azure_tenant_id,
        "google_cloud_project": settings.google_cloud_project,
        "github_org": settings.github_org,
    }
    settings.provider_mode = "live"
    settings.provider_live_operations_enabled = False
    settings.aws_region = "us-east-1"
    settings.azure_tenant_id = ""
    settings.google_cloud_project = "demo-project"
    settings.github_org = "demo-org"
    try:
        configuration = client.get(
            "/providers/configuration", headers={"x-dev-user": "admin@example.local"}
        )
        assert configuration.status_code == 200
        rows = {row["provider"]: row for row in configuration.json()}
        assert rows["amazon_bedrock"]["mode"] == "live"
        assert rows["amazon_bedrock"]["configured"] is True
        assert rows["amazon_bedrock"]["details"]["required_sdks"] == ["boto3"]
        assert rows["amazon_bedrock"]["details"]["missing_sdks"] == []
        assert rows["amazon_bedrock"]["details"]["operation_profile"]["scope"] == (
            "bedrock:InvokeModel,bedrock:InvokeModelWithResponseStream"
        )
        assert rows["azure_openai"]["configured"] is False
        assert rows["azure_openai"]["details"]["missing_fields"] == ["azure_tenant_id"]
        assert rows["azure_openai"]["details"]["required_sdks"] == ["azure.identity", "openai"]
        assert rows["microsoft_foundry"]["details"]["required_sdks"] == [
            "azure.identity",
            "msgraph",
        ]
        assert rows["github_copilot"]["details"]["operations_enabled"] is False
        assert rows["github_copilot"]["details"]["required_sdks"] == ["github"]

        health = client.get("/providers/health", headers={"x-dev-user": "employee@example.local"})
        assert health.status_code == 200
        health_rows = {row["provider"]: row for row in health.json()}
        assert health_rows["amazon_bedrock"]["status"] == "healthy"
        assert health_rows["amazon_bedrock"]["details"]["missing_sdks"] == []
        assert health_rows["azure_openai"]["status"] == "degraded"
    finally:
        for field, value in original_values.items():
            setattr(settings, field, value)


def test_live_provider_operations_create_least_privilege_assignments(
    client: TestClient,
) -> None:
    settings = get_settings()
    original_values = {
        "provider_mode": settings.provider_mode,
        "provider_live_operations_enabled": settings.provider_live_operations_enabled,
        "aws_region": settings.aws_region,
        "github_org": settings.github_org,
    }
    settings.provider_mode = "live"
    settings.provider_live_operations_enabled = True
    settings.aws_region = "us-east-1"
    settings.github_org = "demo-org"
    try:
        provision_demo_request(client)

        assignments = client.get(
            "/provider-assignments", headers={"x-dev-user": "admin@example.local"}
        )
        assert assignments.status_code == 200
        rows = {row["provider"]: row for row in assignments.json()}
        assert rows["amazon_bedrock"]["status"] == "active"
        assert rows["amazon_bedrock"]["external_resource_id"].startswith(
            "live-amazon_bedrock-"
        )
        assert rows["github_copilot"]["external_resource_id"].startswith(
            "live-github_copilot-"
        )

        evidence = client.get(
            "/evidence/provisioning", headers={"x-dev-user": "auditor@example.local"}
        )
        assert evidence.status_code == 200
        evidence_rows = {row["provider"]: row for row in evidence.json()}
        assert evidence_rows["amazon_bedrock"]["provision_job_status"] == "completed"
        assert evidence_rows["github_copilot"]["provision_job_status"] == "completed"
    finally:
        for field, value in original_values.items():
            setattr(settings, field, value)


def test_observability_propagates_trace_and_correlation_ids(client: TestClient) -> None:
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    live = client.get(
        "/health/live",
        headers={"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"},
    )
    assert live.status_code == 200
    assert live.headers["x-trace-id"] == trace_id
    assert live.headers["x-correlation-id"]

    denied = client.get(
        "/providers/configuration",
        headers={
            "x-dev-user": "employee@example.local",
            "x-correlation-id": "observability-correlation",
        },
    )
    assert denied.status_code == 403

    observability = client.get("/health/observability")
    assert observability.status_code == 200
    body = observability.json()
    assert body["status"] == "observable"
    assert body["requests"]["requests_total"] >= 2
    assert body["requests"]["status_counts"]["2xx"] >= 1
    assert body["requests"]["status_counts"]["4xx"] >= 1
    assert body["lifecycle_jobs"]["queued_or_failed"] >= 0

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    failures = [
        event for event in audit.json() if event["event_type"] == "authorization.failure"
    ]
    assert failures[0]["correlation_id"] == "observability-correlation"


def test_rate_limit_returns_correlation_and_retry_headers(client: TestClient) -> None:
    original_limit = rate_limiter.limit
    try:
        rate_limiter.limit = 1
        rate_limiter.reset()
        first = client.get("/health/live", headers={"x-correlation-id": "rate-limit-one"})
        assert first.status_code == 200
        assert first.headers["x-ratelimit-limit"] == "1"
        assert first.headers["x-ratelimit-remaining"] == "0"

        limited = client.get("/health/live", headers={"x-correlation-id": "rate-limit-two"})
        assert limited.status_code == 429
        assert limited.headers["x-correlation-id"] == "rate-limit-two"
        assert limited.headers["x-trace-id"]
        assert limited.headers["x-ratelimit-reset"]
        assert limited.json()["detail"]["code"] == "RATE_LIMITED"
        assert limited.json()["detail"]["correlation_id"] == "rate-limit-two"
    finally:
        rate_limiter.limit = original_limit
        rate_limiter.reset()


def test_provider_webhook_requires_valid_signature(client: TestClient) -> None:
    payload = {
        "provider": "amazon_bedrock",
        "event_type": "budget.threshold",
        "delivery_id": "delivery-1",
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))

    missing_signature = client.post(
        "/webhooks/provider-events",
        content=body,
        headers={"content-type": "application/json"},
    )
    assert missing_signature.status_code == 401

    invalid_signature = client.post(
        "/webhooks/provider-events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-provider-timestamp": timestamp,
            "x-provider-signature": "sha256=invalid",
        },
    )
    assert invalid_signature.status_code == 401

    valid_signature = client.post(
        "/webhooks/provider-events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-correlation-id": "provider-webhook",
            "x-provider-timestamp": timestamp,
            "x-provider-signature": webhook_signature(
                timestamp,
                body,
                get_settings().provider_webhook_secret,
            ),
        },
    )
    assert valid_signature.status_code == 200
    assert valid_signature.json() == {"status": "accepted", "provider": "amazon_bedrock"}

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    webhook_events = [
        event for event in audit.json() if event["event_type"] == "provider.webhook_received"
    ]
    assert webhook_events[0]["correlation_id"] == "provider-webhook"
    assert webhook_events[0]["provider"] == "amazon_bedrock"


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

    export = client.get(
        "/reports/executive/export",
        headers={"x-dev-user": "cto@example.local", "x-correlation-id": "executive-export"},
    )
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(export.text.splitlines()))
    assert {"section", "name", "metric", "value"} <= set(rows[0])
    assert any(
        row["section"] == "summary"
        and row["name"] == "total_spend"
        and row["value"] == "25.00"
        for row in rows
    )
    assert any(
        row["section"] == "cost_center"
        and row["name"] == "ENG-AI"
        and row["metric"] == "remaining_budget"
        and row["value"] == "75.00"
        for row in rows
    )

    denied_export = client.get(
        "/reports/executive/export", headers={"x-dev-user": "employee@example.local"}
    )
    assert denied_export.status_code == 403

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    exported_event = next(
        event for event in audit.json() if event["event_type"] == "report.executive_exported"
    )
    assert exported_event["correlation_id"] == "executive-export"
    assert exported_event["metadata_json"]["row_count"] == len(rows)


def test_privileged_users_can_view_adoption_report_and_export_evidence(
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

    report = client.get("/reports/adoption", headers={"x-dev-user": "auditor@example.local"})
    assert report.status_code == 200
    body = report.json()
    assert body["total_users"] == 8
    assert body["users_with_requests"] == 1
    assert body["projects_with_usage"] == 1
    assert body["active_assignments"] == 2
    assert body["total_tokens"] == 5000
    assert body["total_request_events"] == 10
    assert body["total_spend"] == "25.00"
    assert body["adoption_by_department"][0]["name"] == "Engineering"
    assert body["adoption_by_department"][0]["request_count"] == 1
    assert any(
        provider["name"] == assignments[0]["provider"]
        and provider["active_assignments"] == 1
        and provider["total_tokens"] == 5000
        for provider in body["adoption_by_provider"]
    )
    assert body["project_activity"][0]["project_name"] == "Interview Demo Sandbox"
    assert body["project_activity"][0]["member_count"] == 2

    admin_report = client.get("/reports/adoption", headers={"x-dev-user": "admin@example.local"})
    cto_report = client.get("/reports/adoption", headers={"x-dev-user": "cto@example.local"})
    denied_report = client.get(
        "/reports/adoption", headers={"x-dev-user": "employee@example.local"}
    )
    assert admin_report.status_code == 200
    assert cto_report.status_code == 200
    assert denied_report.status_code == 403

    export = client.get(
        "/reports/adoption/export",
        headers={"x-dev-user": "auditor@example.local", "x-correlation-id": "adoption-export"},
    )
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(export.text.splitlines()))
    assert {"section", "name", "metric", "value"} <= set(rows[0])
    assert any(
        row["section"] == "summary"
        and row["name"] == "total_tokens"
        and row["value"] == "5000"
        for row in rows
    )
    assert any(
        row["section"] == "project"
        and row["name"] == "Interview Demo Sandbox"
        and row["metric"] == "member_count"
        and row["value"] == "2"
        for row in rows
    )

    audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
    exported_event = next(
        event for event in audit.json() if event["event_type"] == "report.adoption_exported"
    )
    assert exported_event["correlation_id"] == "adoption-export"
    assert exported_event["metadata_json"]["row_count"] == len(rows)


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


def test_worker_drains_queued_cost_allocation_delivery(client: TestClient) -> None:
    settings = get_settings()
    original_inline_execution = settings.lifecycle_inline_execution
    provision_demo_request(client)
    try:
        settings.lifecycle_inline_execution = False
        delivery = client.post(
            "/reports/cost-allocation/deliveries",
            headers={"x-dev-user": "cto@example.local", "x-correlation-id": "queued-delivery"},
            json={"frequency": "weekly", "recipients": ["finance@example.local"]},
        )
        assert delivery.status_code == 201
        assert delivery.json()["status"] == "queued"
        assert delivery.json()["row_count"] == 0

        jobs = client.get("/lifecycle-jobs", headers={"x-dev-user": "admin@example.local"}).json()
        report_job = next(job for job in jobs if job["job_type"] == "cost_allocation_delivery")
        assert report_job["payload"]["correlation_id"] == "queued-delivery"

        assert asyncio.run(drain_once(limit=10)) == 1
        deliveries = client.get(
            "/reports/cost-allocation/deliveries",
            headers={"x-dev-user": "auditor@example.local"},
        )
        assert deliveries.status_code == 200
        assert deliveries.json()[0]["status"] == "completed"
        assert deliveries.json()[0]["row_count"] == 2

        audit = client.get("/audit-events", headers={"x-dev-user": "auditor@example.local"})
        assert {
            "report.cost_allocation_delivery_scheduled",
            "report.cost_allocation_delivery_completed",
        } <= {event["event_type"] for event in audit.json()}
    finally:
        settings.lifecycle_inline_execution = original_inline_execution


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
