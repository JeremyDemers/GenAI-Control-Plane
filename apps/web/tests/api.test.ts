import { afterEach, describe, expect, it, vi } from "vitest";

import { getAuditEventSummary, scanExpirationWarnings } from "@/lib/api";
import { apiBaseUrl, apiDocsUrl } from "@/lib/api-config";

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

describe("api helpers", () => {
  afterEach(() => {
    if (originalApiUrl === undefined) {
      delete process.env.NEXT_PUBLIC_API_URL;
    } else {
      process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
    }
    vi.unstubAllGlobals();
  });

  it("builds the FastAPI docs URL from the configured API base", () => {
    expect(apiDocsUrl()).toBe("http://localhost:8000/docs");
  });

  it("normalizes trailing slashes from the configured API base", () => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8010///";

    expect(apiBaseUrl()).toBe("http://localhost:8010");
    expect(apiDocsUrl()).toBe("http://localhost:8010/docs");
  });

  it("requests filtered audit summaries with dev identity headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          total_events: 1,
          unique_correlations: 1,
          success_events: 1,
          failure_events: 0,
          by_event_type: [{ name: "notification.read", count: 1 }],
          by_result: [{ name: "success", count: 1 }]
        })
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      getAuditEventSummary("auditor@example.local", {
        event_type: "notification.read",
        correlation_id: "notification-read"
      })
    ).resolves.toMatchObject({ total_events: 1 });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/audit-events/summary?event_type=notification.read&correlation_id=notification-read",
      expect.objectContaining({
        headers: expect.objectContaining({ "x-dev-user": "auditor@example.local" })
      })
    );
  });

  it("requests expiration warning scans as an admin action", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          id: "job-1",
          job_type: "access_expiration_scan",
          status: "completed",
          attempt_count: 1,
          idempotency_key: "expiration-warning:test",
          payload: { warned_count: 2 },
          failure_information: {},
          created_at: "2026-07-15T00:00:00Z",
          updated_at: "2026-07-15T00:00:00Z"
        })
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(scanExpirationWarnings("admin@example.local")).resolves.toMatchObject({
      job_type: "access_expiration_scan",
      status: "completed"
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/developer/assignments/expiration-warnings",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "x-dev-user": "admin@example.local" })
      })
    );
  });
});
