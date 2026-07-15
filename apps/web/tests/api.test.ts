import { describe, expect, it } from "vitest";

import { apiDocsUrl } from "@/lib/api";

describe("api helpers", () => {
  it("builds the FastAPI docs URL from the configured API base", () => {
    expect(apiDocsUrl()).toBe("http://localhost:8000/docs");
  });
});
