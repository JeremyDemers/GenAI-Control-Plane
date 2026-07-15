import { evidencePanelState, type EvidencePanelState } from "@/lib/evidence-state";

export function approvalQueuePanelState({
  canReviewApprovals,
  count,
  isError,
  isLoading
}: {
  canReviewApprovals: boolean;
  count: number | undefined;
  isError: boolean;
  isLoading: boolean;
}): EvidencePanelState {
  return evidencePanelState({
    count: canReviewApprovals ? count : 0,
    isError: canReviewApprovals && isError,
    isLoading: canReviewApprovals && isLoading
  });
}
