export type NotificationPanelState = "loading" | "error" | "empty" | "ready";

export function notificationPanelState({
  count,
  isError,
  isLoading
}: {
  count: number | undefined;
  isError: boolean;
  isLoading: boolean;
}): NotificationPanelState {
  if (isLoading) {
    return "loading";
  }
  if (isError) {
    return "error";
  }
  return (count ?? 0) === 0 ? "empty" : "ready";
}
