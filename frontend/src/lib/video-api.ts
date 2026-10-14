import "server-only";

import { auth } from "@clerk/nextjs/server";

export function videoApiBase(): string {
  const raw = process.env.VIDEO_API_BASE_URL;
  if (!raw) throw new Error("VIDEO_API_BASE_URL is required");
  const url = new URL(raw);
  if (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname))) {
    throw new Error("Remote VIDEO_API_BASE_URL must use HTTPS");
  }
  return url.origin;
}

export function sameOrigin(request: Request): boolean {
  const origin = process.env.APP_ORIGIN;
  return Boolean(origin && request.headers.get("origin") === new URL(origin).origin);
}

export async function sessionToken(): Promise<string | null> {
  const session = await auth();
  if (!session.userId) return null;
  return session.getToken();
}
