import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pythonjsonlogger.json import JsonFormatter

from app.core.config import get_settings


def trace_id_from_traceparent(traceparent: str | None) -> str | None:
    if not traceparent:
        return None
    parts = traceparent.split("-")
    if len(parts) < 4:
        return None
    trace_id = parts[1]
    if len(trace_id) != 32 or not all(character in "0123456789abcdef" for character in trace_id):
        return None
    return trace_id


@dataclass
class RequestMetrics:
    requests_total: int = 0
    status_counts: dict[str, int] = field(default_factory=dict)
    route_counts: dict[str, int] = field(default_factory=dict)
    total_duration_ms: float = 0
    max_duration_ms: float = 0

    def record(self, *, path: str, status_code: int, duration_ms: float) -> None:
        self.requests_total += 1
        status_family = f"{status_code // 100}xx"
        self.status_counts[status_family] = self.status_counts.get(status_family, 0) + 1
        self.route_counts[path] = self.route_counts.get(path, 0) + 1
        self.total_duration_ms += duration_ms
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)

    def snapshot(self) -> dict[str, object]:
        average_duration_ms = (
            round(self.total_duration_ms / self.requests_total, 2)
            if self.requests_total
            else 0
        )
        return {
            "requests_total": self.requests_total,
            "status_counts": dict(sorted(self.status_counts.items())),
            "top_routes": dict(
                sorted(self.route_counts.items(), key=lambda item: item[1], reverse=True)[:10]
            ),
            "average_duration_ms": average_duration_ms,
            "max_duration_ms": round(self.max_duration_ms, 2),
        }


request_metrics = RequestMetrics()


@dataclass
class RateLimiter:
    limit: int
    window_seconds: int = 60
    buckets: dict[str, tuple[int, int]] = field(default_factory=dict)

    def check(self, key: str, now: int | None = None) -> tuple[bool, int, int]:
        current_time = now or int(time.time())
        window_start = current_time - (current_time % self.window_seconds)
        stored_window, count = self.buckets.get(key, (window_start, 0))
        if stored_window != window_start:
            stored_window = window_start
            count = 0
        count += 1
        self.buckets[key] = (stored_window, count)
        remaining = max(self.limit - count, 0)
        reset_at = stored_window + self.window_seconds
        return count <= self.limit, remaining, reset_at

    def reset(self) -> None:
        self.buckets.clear()


rate_limiter = RateLimiter(limit=get_settings().rate_limit_requests_per_minute)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


async def correlation_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    correlation_id = request.headers.get("x-correlation-id") or str(uuid4())
    trace_id = trace_id_from_traceparent(request.headers.get("traceparent")) or uuid4().hex
    request.state.correlation_id = correlation_id
    request.state.trace_id = trace_id
    start = time.perf_counter()
    rate_limit_key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
    allowed, remaining, reset_at = rate_limiter.check(rate_limit_key)
    if allowed:
        response = await call_next(request)
    else:
        response = JSONResponse(
            status_code=429,
            content={
                "detail": {
                    "code": "RATE_LIMITED",
                    "message": "Too many requests.",
                    "correlation_id": correlation_id,
                }
            },
        )
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["x-correlation-id"] = correlation_id
    response.headers["x-trace-id"] = trace_id
    response.headers["x-ratelimit-limit"] = str(rate_limiter.limit)
    response.headers["x-ratelimit-remaining"] = str(remaining)
    response.headers["x-ratelimit-reset"] = str(reset_at)
    request_metrics.record(
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    logging.getLogger("api.access").info(
        "request.completed",
        extra={
            "correlation_id": correlation_id,
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response
