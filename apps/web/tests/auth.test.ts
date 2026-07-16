import { afterEach, describe, expect, it, vi } from "vitest";

import {
  clearOidcSession,
  decodeJwtClaims,
  emailFromClaims,
  loadOidcSession,
  oidcConfig,
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
  const originalAuthEndpoint = process.env.NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT;
  const originalClientId = process.env.NEXT_PUBLIC_OIDC_CLIENT_ID;
  const originalMicrosoftTenantId = process.env.NEXT_PUBLIC_MICROSOFT_TENANT_ID;

  afterEach(() => {
    process.env.NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT = originalAuthEndpoint;
    process.env.NEXT_PUBLIC_OIDC_CLIENT_ID = originalClientId;
    process.env.NEXT_PUBLIC_MICROSOFT_TENANT_ID = originalMicrosoftTenantId;
  });

  it("derives Microsoft Entra authorization settings from a tenant id", () => {
    delete process.env.NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT;
    process.env.NEXT_PUBLIC_OIDC_CLIENT_ID = "client-id";
    process.env.NEXT_PUBLIC_MICROSOFT_TENANT_ID = "tenant-id";

    expect(oidcConfig()).toMatchObject({
      authorizationEndpoint:
        "https://login.microsoftonline.com/tenant-id/oauth2/v2.0/authorize",
      clientId: "client-id",
      providerLabel: "Microsoft"
    });
  });

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
