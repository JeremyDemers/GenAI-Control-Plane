export function apiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export function apiDocsUrl() {
  return `${apiBaseUrl()}/docs`;
}
