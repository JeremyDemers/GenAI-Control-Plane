import { describe, expect, it } from "vitest";

import { approvalQueuePanelState } from "@/lib/approval-queue-state";

describe("approvalQueuePanelState", () => {
  it("ignores stale approval query errors when the current role cannot review approvals", () => {
    expect(
      approvalQueuePanelState({
        canReviewApprovals: false,
        count: undefined,
        isError: true,
        isLoading: false
      })
    ).toBe("empty");
  });

  it("keeps approval query errors visible for approval reviewers", () => {
    expect(
      approvalQueuePanelState({
        canReviewApprovals: true,
        count: undefined,
        isError: true,
        isLoading: false
      })
    ).toBe("error");
  });
});
