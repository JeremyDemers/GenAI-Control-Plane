export type EvidencePanelState = "loading" | "error" | "empty" | "ready";

export function evidencePanelState({
  count,
  isError,
  isLoading
}: {
  count: number | undefined;
  isError: boolean;
  isLoading: boolean;
}): EvidencePanelState {
  if (isLoading) {
    return "loading";
  }
  if (isError) {
    return "error";
  }
  return (count ?? 0) === 0 ? "empty" : "ready";
}
