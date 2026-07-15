import { afterEach, describe, expect, it } from "vitest";

import { apiBaseUrl, apiDocsUrl } from "@/lib/api-config";

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

describe("api helpers", () => {
  afterEach(() => {
    process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
  });

  it("builds the FastAPI docs URL from the configured API base", () => {
    expect(apiDocsUrl()).toBe("http://localhost:8000/docs");
  });

  it("normalizes trailing slashes from the configured API base", () => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8010///";

    expect(apiBaseUrl()).toBe("http://localhost:8010");
    expect(apiDocsUrl()).toBe("http://localhost:8010/docs");
  });
});
