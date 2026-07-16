import { apiBaseUrl } from "@/lib/api-config";

export type AuthMode = "development" | "oidc";

export type OidcConfig = {
  authorizationEndpoint: string;
  clientId: string;
  redirectUri: string;
  scope: string;
  apiBaseUrl: string;
  providerLabel: string;
};

export type OidcSession = {
  accessToken: string;
  email: string;
  expiresAt: number;
};

const verifierKey = "genai-control-plane:pkce-verifier";
const stateKey = "genai-control-plane:pkce-state";
const sessionKey = "genai-control-plane:oidc-session";

export function authMode(): AuthMode {
  return process.env.NEXT_PUBLIC_AUTH_MODE === "oidc" ? "oidc" : "development";
}

export function oidcConfig(): OidcConfig | null {
  const microsoftTenantId = process.env.NEXT_PUBLIC_MICROSOFT_TENANT_ID?.trim();
  const authorizationEndpoint =
    process.env.NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT ||
    (microsoftTenantId
      ? `https://login.microsoftonline.com/${microsoftTenantId}/oauth2/v2.0/authorize`
      : undefined);
  const clientId = process.env.NEXT_PUBLIC_OIDC_CLIENT_ID;
  if (!authorizationEndpoint || !clientId) {
    return null;
  }
  return {
    authorizationEndpoint,
    clientId,
    redirectUri:
      process.env.NEXT_PUBLIC_OIDC_REDIRECT_URI ??
      (typeof window === "undefined" ? "" : window.location.origin),
    scope: process.env.NEXT_PUBLIC_OIDC_SCOPE ?? "openid profile email offline_access",
    apiBaseUrl: apiBaseUrl(),
    providerLabel: authorizationEndpoint.includes("login.microsoftonline.com")
      ? "Microsoft"
      : "enterprise identity provider"
  };
}

export async function beginOidcLogin(config: OidcConfig) {
  const verifier = base64UrlEncode(crypto.getRandomValues(new Uint8Array(32)));
  const state = base64UrlEncode(crypto.getRandomValues(new Uint8Array(32)));
  const challenge = await pkceChallenge(verifier);

  sessionStorage.setItem(verifierKey, verifier);
  sessionStorage.setItem(stateKey, state);

  const url = new URL(config.authorizationEndpoint);
  url.searchParams.set("client_id", config.clientId);
  url.searchParams.set("redirect_uri", config.redirectUri);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", config.scope);
  url.searchParams.set("state", state);
  url.searchParams.set("code_challenge", challenge);
  url.searchParams.set("code_challenge_method", "S256");
  window.location.assign(url.toString());
}

export async function completeOidcLogin(search: string, config: OidcConfig): Promise<OidcSession | null> {
  const params = new URLSearchParams(search);
  const code = params.get("code");
  const state = params.get("state");
  if (!code || !state) {
    return null;
  }
  if (state !== sessionStorage.getItem(stateKey)) {
    throw new Error("OIDC state did not match the pending login.");
  }
  const verifier = sessionStorage.getItem(verifierKey);
  if (!verifier) {
    throw new Error("OIDC PKCE verifier is missing.");
  }

  const response = await fetch(`${config.apiBaseUrl}/auth/oidc/callback`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      code,
      redirect_uri: config.redirectUri,
      code_verifier: verifier
    })
  });
  if (!response.ok) {
    throw new Error(await authErrorMessage(response, "OIDC session exchange failed"));
  }

  const payload = (await response.json()) as {
    access_token?: string;
    expires_at?: string;
    user?: { email?: string };
  };
  if (!payload.access_token) {
    throw new Error("OIDC session response did not include an access token.");
  }

  const email =
    payload.user?.email?.trim().toLowerCase() ??
    emailFromClaims(decodeJwtClaims(payload.access_token));
  const expiresAt = payload.expires_at ? Date.parse(payload.expires_at) : Date.now() + 900_000;
  const session = {
    accessToken: payload.access_token,
    email,
    expiresAt
  };
  saveOidcSession(session);
  sessionStorage.removeItem(verifierKey);
  sessionStorage.removeItem(stateKey);
  return session;
}

export async function refreshOidcSession(config: OidcConfig): Promise<OidcSession | null> {
  const response = await fetch(`${config.apiBaseUrl}/auth/oidc/refresh`, {
    method: "POST",
    credentials: "include"
  });
  if (!response.ok) {
    clearOidcSession();
    return null;
  }
  const payload = (await response.json()) as {
    access_token?: string;
    expires_at?: string;
    user?: { email?: string };
  };
  if (!payload.access_token || !payload.user?.email) {
    clearOidcSession();
    return null;
  }
  const session = {
    accessToken: payload.access_token,
    email: payload.user.email.trim().toLowerCase(),
    expiresAt: payload.expires_at ? Date.parse(payload.expires_at) : Date.now() + 900_000
  };
  saveOidcSession(session);
  return session;
}

export function loadOidcSession(): OidcSession | null {
  if (typeof sessionStorage === "undefined") {
    return null;
  }
  const raw = sessionStorage.getItem(sessionKey);
  if (!raw) {
    return null;
  }
  const session = JSON.parse(raw) as OidcSession;
  if (session.expiresAt <= Date.now() + 30_000) {
    clearOidcSession();
    return null;
  }
  return session;
}

export function saveOidcSession(session: OidcSession) {
  sessionStorage.setItem(sessionKey, JSON.stringify(session));
}

export function clearOidcSession() {
  sessionStorage.removeItem(sessionKey);
}

export async function authErrorMessage(response: Response, fallback: string) {
  const fallbackMessage = `${fallback}: ${response.status}`;
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      const payload = (await response.json()) as {
        detail?: string | { message?: string; code?: string };
        message?: string;
      };
      const detail = payload.detail;
      const message =
        typeof detail === "string" ? detail : detail?.message ?? payload.message;

      return message?.trim() ? `${fallback}: ${message.trim()}` : fallbackMessage;
    } catch {
      return fallbackMessage;
    }
  }

  try {
    const text = await response.text();
    return text.trim() ? `${fallback}: ${text.trim()}` : fallbackMessage;
  } catch {
    return fallbackMessage;
  }
}

export async function logoutOidcSession(config: OidcConfig) {
  await fetch(`${config.apiBaseUrl}/auth/logout`, {
    method: "POST",
    credentials: "include"
  }).catch(() => undefined);
  clearOidcSession();
}

export function decodeJwtClaims(token: string): Record<string, unknown> {
  const [, payload] = token.split(".");
  if (!payload) {
    return {};
  }
  const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return JSON.parse(atob(padded)) as Record<string, unknown>;
}

export function emailFromClaims(claims: Record<string, unknown>) {
  for (const claimName of ["email", "preferred_username", "upn"]) {
    const value = claims[claimName];
    if (typeof value === "string" && value.trim()) {
      return value.trim().toLowerCase();
    }
  }
  throw new Error("OIDC token did not include an email claim.");
}

async function pkceChallenge(verifier: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return base64UrlEncode(new Uint8Array(digest));
}

function base64UrlEncode(bytes: Uint8Array) {
  const base64 = btoa(String.fromCharCode(...bytes));
  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}
