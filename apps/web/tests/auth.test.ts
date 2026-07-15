import { describe, expect, it, vi } from "vitest";

import {
  clearOidcSession,
  decodeJwtClaims,
  emailFromClaims,
  loadOidcSession,
  saveOidcSession,
  type OidcSession
} from "@/lib/auth";

function tokenWithClaims(claims: Record<string, unknown>) {
  const encodedClaims = btoa(JSON.stringify(claims))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/u, "");
  return `header.${encodedClaims}.signature`;
}

describe("OIDC auth helpers", () => {
  it("decodes JWT claims and selects a supported email claim", () => {
    const claims = decodeJwtClaims(
      tokenWithClaims({ preferred_username: "Employee@Example.Local" })
    );

    expect(emailFromClaims(claims)).toBe("employee@example.local");
  });

  it("expires session-scoped OIDC tokens before reuse", () => {
    const now = new Date("2026-01-01T00:00:00Z").getTime();
    vi.useFakeTimers();
    vi.setSystemTime(now);
    const session: OidcSession = {
      accessToken: "access-token",
      idToken: null,
      email: "employee@example.local",
      expiresAt: now - 1
    };

    saveOidcSession(session);

    expect(loadOidcSession()).toBeNull();
    expect(sessionStorage.length).toBe(0);

    vi.useRealTimers();
    clearOidcSession();
  });
});
