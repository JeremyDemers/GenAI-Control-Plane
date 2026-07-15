export type AuthMode = "development" | "oidc";

export type OidcConfig = {
  authorizationEndpoint: string;
  tokenEndpoint: string;
  clientId: string;
  redirectUri: string;
  scope: string;
};

export type OidcSession = {
  accessToken: string;
  idToken: string | null;
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
  const authorizationEndpoint = process.env.NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT;
  const tokenEndpoint = process.env.NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT;
  const clientId = process.env.NEXT_PUBLIC_OIDC_CLIENT_ID;
  if (!authorizationEndpoint || !tokenEndpoint || !clientId) {
    return null;
  }
  return {
    authorizationEndpoint,
    tokenEndpoint,
    clientId,
    redirectUri:
      process.env.NEXT_PUBLIC_OIDC_REDIRECT_URI ??
      (typeof window === "undefined" ? "" : window.location.origin),
    scope: process.env.NEXT_PUBLIC_OIDC_SCOPE ?? "openid profile email"
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

  const response = await fetch(config.tokenEndpoint, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config.clientId,
      code,
      redirect_uri: config.redirectUri,
      code_verifier: verifier
    })
  });
  if (!response.ok) {
    throw new Error(`OIDC token exchange failed: ${response.status}`);
  }

  const payload = (await response.json()) as {
    access_token?: string;
    id_token?: string;
    expires_in?: number;
  };
  if (!payload.access_token) {
    throw new Error("OIDC token response did not include an access token.");
  }

  const claims = decodeJwtClaims(payload.id_token ?? payload.access_token);
  const email = emailFromClaims(claims);
  const expiresAt = Date.now() + Math.max(payload.expires_in ?? 900, 60) * 1000;
  const session = {
    accessToken: payload.access_token,
    idToken: payload.id_token ?? null,
    email,
    expiresAt
  };
  saveOidcSession(session);
  sessionStorage.removeItem(verifierKey);
  sessionStorage.removeItem(stateKey);
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
