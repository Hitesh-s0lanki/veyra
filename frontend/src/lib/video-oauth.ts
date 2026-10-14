import "server-only";

import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";
import { auth } from "@clerk/nextjs/server";
import { cookies } from "next/headers";

const PENDING_COOKIE = "video_oauth_pending";
const TOKEN_COOKIE = "video_oauth_tokens";

type Pending = { state: string; verifier: string; userId: string; expiresAt: number };
type Tokens = { accessToken: string; refreshToken?: string; expiresAt: number; userId: string };
type TokenResponse = { access_token: string; refresh_token?: string; expires_in: number; token_type: string };

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

export function oauthConfig() {
  const issuer = new URL(required("CLERK_OAUTH_ISSUER"));
  const appOrigin = new URL(required("APP_ORIGIN"));
  const apiBase = new URL(required("VIDEO_API_BASE_URL"));
  if (issuer.protocol !== "https:" || issuer.pathname !== "/" || issuer.search || issuer.hash) {
    throw new Error("CLERK_OAUTH_ISSUER must be an HTTPS origin");
  }
  if ((appOrigin.protocol !== "https:" && appOrigin.hostname !== "localhost") || appOrigin.pathname !== "/") {
    throw new Error("APP_ORIGIN must be an HTTPS origin or localhost");
  }
  if (apiBase.protocol !== "https:" && !(apiBase.protocol === "http:" && ["localhost", "127.0.0.1"].includes(apiBase.hostname))) {
    throw new Error("Remote VIDEO_API_BASE_URL must use HTTPS");
  }
  return {
    issuer: issuer.origin,
    appOrigin: appOrigin.origin,
    apiBase: apiBase.origin,
    clientId: required("CLERK_OAUTH_CLIENT_ID"),
    clientSecret: required("CLERK_OAUTH_CLIENT_SECRET"),
    redirectUri: `${appOrigin.origin}/api/oauth/callback`,
  };
}

function encryptionKey(): Buffer {
  const hex = required("OAUTH_COOKIE_SECRET");
  if (!/^[0-9a-fA-F]{64}$/.test(hex)) throw new Error("OAUTH_COOKIE_SECRET must be 32 random bytes as hex");
  return Buffer.from(hex, "hex");
}

function seal(value: Pending | Tokens): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", encryptionKey(), iv);
  const body = Buffer.concat([cipher.update(JSON.stringify(value), "utf8"), cipher.final()]);
  return Buffer.concat([iv, cipher.getAuthTag(), body]).toString("base64url");
}

function open<T>(value: string | undefined): T | null {
  if (!value) return null;
  try {
    const bytes = Buffer.from(value, "base64url");
    if (bytes.length < 29) return null;
    const decipher = createDecipheriv("aes-256-gcm", encryptionKey(), bytes.subarray(0, 12));
    decipher.setAuthTag(bytes.subarray(12, 28));
    return JSON.parse(Buffer.concat([decipher.update(bytes.subarray(28)), decipher.final()]).toString("utf8")) as T;
  } catch {
    return null;
  }
}

function cookieOptions(maxAge: number) {
  return { httpOnly: true, secure: oauthConfig().appOrigin.startsWith("https:"), sameSite: "lax" as const, path: "/", maxAge };
}

export async function startAuthorization(userId: string): Promise<string> {
  const config = oauthConfig();
  const verifier = randomBytes(32).toString("base64url");
  const state = randomBytes(32).toString("base64url");
  const challenge = createHash("sha256").update(verifier).digest("base64url");
  const pending: Pending = { verifier, state, userId, expiresAt: Date.now() + 10 * 60_000 };
  (await cookies()).set(PENDING_COOKIE, seal(pending), cookieOptions(600));
  const url = new URL(`${config.issuer}/oauth/authorize`);
  url.search = new URLSearchParams({
    response_type: "code", client_id: config.clientId, redirect_uri: config.redirectUri,
    scope: "profile offline_access", state, code_challenge: challenge, code_challenge_method: "S256",
  }).toString();
  return url.toString();
}

async function postToken(fields: Record<string, string>): Promise<TokenResponse> {
  const config = oauthConfig();
  const response = await fetch(`${config.issuer}/oauth/token`, {
    method: "POST", cache: "no-store",
    headers: {
      Authorization: `Basic ${Buffer.from(`${config.clientId}:${config.clientSecret}`).toString("base64")}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams(fields),
  });
  if (!response.ok) throw new Error("OAuth token exchange failed");
  const data = await response.json() as TokenResponse;
  if (!data.access_token || data.token_type.toLowerCase() !== "bearer" || !Number.isFinite(data.expires_in)) {
    throw new Error("Invalid OAuth token response");
  }
  return data;
}

async function tokenSubject(accessToken: string): Promise<string> {
  const config = oauthConfig();
  const response = await fetch(`${config.issuer}/oauth/token_info`, {
    method: "POST", cache: "no-store",
    headers: {
      Authorization: `Basic ${Buffer.from(`${config.clientId}:${config.clientSecret}`).toString("base64")}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ token: accessToken }),
  });
  if (!response.ok) throw new Error("OAuth token validation failed");
  const info = await response.json() as { active?: boolean; sub?: string; client_id?: string; scope?: string };
  if (info.active !== true || info.client_id !== config.clientId || !info.scope?.split(" ").includes("profile") || !info.sub) {
    throw new Error("OAuth token does not belong to this application");
  }
  return info.sub;
}

export async function completeAuthorization(code: string, state: string, userId: string): Promise<void> {
  const store = await cookies();
  const pending = open<Pending>(store.get(PENDING_COOKIE)?.value);
  store.delete(PENDING_COOKIE);
  if (!pending || pending.state !== state || pending.userId !== userId || pending.expiresAt < Date.now()) {
    throw new Error("OAuth state is invalid or expired");
  }
  const token = await postToken({
    grant_type: "authorization_code", code, code_verifier: pending.verifier,
    redirect_uri: oauthConfig().redirectUri,
  });
  if (await tokenSubject(token.access_token) !== userId) throw new Error("OAuth account does not match the signed-in user");
  const saved: Tokens = {
    accessToken: token.access_token, refreshToken: token.refresh_token,
    expiresAt: Date.now() + token.expires_in * 1000, userId,
  };
  store.set(TOKEN_COOKIE, seal(saved), cookieOptions(30 * 24 * 3600));
}

export async function accessTokenForCurrentUser(): Promise<string | null> {
  const { userId } = await auth();
  if (!userId) return null;
  const store = await cookies();
  const saved = open<Tokens>(store.get(TOKEN_COOKIE)?.value);
  if (!saved || saved.userId !== userId) return null;
  if (saved.expiresAt > Date.now() + 60_000) return saved.accessToken;
  if (!saved.refreshToken) {
    store.delete(TOKEN_COOKIE);
    return null;
  }
  try {
    const refreshed = await postToken({ grant_type: "refresh_token", refresh_token: saved.refreshToken });
    if (await tokenSubject(refreshed.access_token) !== userId) throw new Error("OAuth account changed");
    const updated: Tokens = {
      accessToken: refreshed.access_token, refreshToken: refreshed.refresh_token ?? saved.refreshToken,
      expiresAt: Date.now() + refreshed.expires_in * 1000, userId,
    };
    store.set(TOKEN_COOKIE, seal(updated), cookieOptions(30 * 24 * 3600));
    return updated.accessToken;
  } catch {
    store.delete(TOKEN_COOKIE);
    return null;
  }
}

export async function disconnect(): Promise<void> {
  const { userId } = await auth();
  const store = await cookies();
  const saved = open<Tokens>(store.get(TOKEN_COOKIE)?.value);
  if (saved && saved.userId === userId) {
    const config = oauthConfig();
    const response = await fetch(`${config.issuer}/oauth/token/revoke`, {
      method: "POST", cache: "no-store",
      headers: {
        Authorization: `Basic ${Buffer.from(`${config.clientId}:${config.clientSecret}`).toString("base64")}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({ token: saved.refreshToken ?? saved.accessToken }),
    });
    if (!response.ok) throw new Error("OAuth revocation failed");
  }
  store.delete(TOKEN_COOKIE);
}

export function sameOrigin(request: Request): boolean {
  return request.headers.get("origin") === oauthConfig().appOrigin;
}
