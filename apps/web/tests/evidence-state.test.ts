import { describe, expect, it } from "vitest";

import { evidencePanelState } from "@/lib/evidence-state";

describe("evidencePanelState", () => {
  it("treats an empty successful response as an empty state", () => {
    expect(evidencePanelState({ count: 0, isError: false, isLoading: false })).toBe(
      "empty"
    );
  });

  it("shows an error when any evidence request fails", () => {
    expect(evidencePanelState({ count: undefined, isError: true, isLoading: false })).toBe(
      "error"
    );
  });

  it("prefers loading while evidence requests are in flight", () => {
    expect(evidencePanelState({ count: 0, isError: true, isLoading: true })).toBe(
      "loading"
    );
  });
});
