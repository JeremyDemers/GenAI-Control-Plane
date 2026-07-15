import { describe, expect, it } from "vitest";

import { notificationPanelState } from "@/lib/notification-state";

describe("notificationPanelState", () => {
  it("treats an empty successful response as an empty state", () => {
    expect(notificationPanelState({ count: 0, isError: false, isLoading: false })).toBe(
      "empty"
    );
  });

  it("shows an error only when the notification request fails", () => {
    expect(notificationPanelState({ count: undefined, isError: true, isLoading: false })).toBe(
      "error"
    );
  });

  it("prefers loading before empty or error text", () => {
    expect(notificationPanelState({ count: 0, isError: true, isLoading: true })).toBe(
      "loading"
    );
  });
});
