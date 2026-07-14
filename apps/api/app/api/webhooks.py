import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_correlation_id
from app.core.config import get_settings
from app.core.database import get_db
from app.services.audit import record_audit_event

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

SIGNATURE_PREFIX = "sha256="
SIGNATURE_WINDOW_SECONDS = 300


def webhook_signature(timestamp: str, body: bytes, secret: str) -> str:
    digest = hmac.new(
        secret.encode(),
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def verify_webhook_signature(
    *,
    body: bytes,
    timestamp: str | None,
    signature: str | None,
    secret: str,
    now: int | None = None,
) -> None:
    if not timestamp or not signature:
        raise HTTPException(
            status_code=401,
            detail={"code": "WEBHOOK_SIGNATURE_REQUIRED", "message": "Missing signature."},
        )
    try:
        timestamp_value = int(timestamp)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "WEBHOOK_SIGNATURE_INVALID", "message": "Invalid timestamp."},
        ) from exc
    current_time = now or int(time.time())
    if abs(current_time - timestamp_value) > SIGNATURE_WINDOW_SECONDS:
        raise HTTPException(
            status_code=401,
            detail={"code": "WEBHOOK_SIGNATURE_STALE", "message": "Stale signature."},
        )
    expected = webhook_signature(timestamp, body, secret)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=401,
            detail={"code": "WEBHOOK_SIGNATURE_INVALID", "message": "Invalid signature."},
        )


def parse_webhook_payload(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "WEBHOOK_PAYLOAD_INVALID", "message": "Invalid JSON payload."},
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail={"code": "WEBHOOK_PAYLOAD_INVALID", "message": "Payload must be an object."},
        )
    provider = payload.get("provider")
    event_type = payload.get("event_type")
    if not isinstance(provider, str) or not isinstance(event_type, str):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "WEBHOOK_PAYLOAD_INVALID",
                "message": "provider and event_type are required strings.",
            },
        )
    return payload


@router.post("/provider-events")
async def provider_events(
    request: Request,
    db: Session = Depends(get_db),
    correlation_id: str = Depends(get_correlation_id),
    x_provider_timestamp: str | None = Header(default=None),
    x_provider_signature: str | None = Header(default=None),
) -> dict[str, str]:
    body = await request.body()
    verify_webhook_signature(
        body=body,
        timestamp=x_provider_timestamp,
        signature=x_provider_signature,
        secret=get_settings().provider_webhook_secret,
    )
    payload = parse_webhook_payload(body)
    record_audit_event(
        db,
        event_type="provider.webhook_received",
        actor_user_id=None,
        target_type="provider_webhook",
        target_id=str(payload["event_type"]),
        action="receive_webhook",
        result="accepted",
        correlation_id=correlation_id,
        provider=str(payload["provider"]),
        metadata_json={
            "provider_event_type": payload["event_type"],
            "delivery_id": payload.get("delivery_id", ""),
        },
    )
    db.commit()
    return {"status": "accepted", "provider": str(payload["provider"])}
