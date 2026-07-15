import { afterEach, describe, expect, it, vi } from "vitest";

import { getAuditEventSummary } from "@/lib/api";
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
});
