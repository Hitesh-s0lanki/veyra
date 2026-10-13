import { sameOrigin, sessionToken, videoApiBase } from "@/lib/video-api";
import { matchVideoApiRoute } from "@/lib/video-api-routes";

type Context = { params: Promise<{ path: string[] }> };

// The API waits up to 90 seconds for Gemini image generation; keep the proxy
// patient for creative routes instead of aborting at the default 30 seconds.
const DEFAULT_TIMEOUT_MS = 30_000;
const CREATIVE_TIMEOUT_MS = 120_000;

async function proxy(request: Request, context: Context, method: "GET" | "POST") {
  if (method === "POST" && !sameOrigin(request)) return Response.json({ detail: "Invalid origin" }, { status: 403 });
  const path = (await context.params).path;
  const target = matchVideoApiRoute(method, path);
  if (!target) return Response.json({ detail: "Route not found" }, { status: 404 });
  const token = await sessionToken();
  if (!token) return Response.json({ detail: "Sign in to use the video studio" }, { status: 401 });
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  let body: string | undefined;
  if (method === "POST") {
    if (request.headers.get("content-type")?.split(";")[0] !== "application/json") {
      return Response.json({ detail: "JSON body required" }, { status: 415 });
    }
    body = await request.text();
    if (body.length > 8192) return Response.json({ detail: "Request too large" }, { status: 413 });
    headers["Content-Type"] = "application/json";
    const key = request.headers.get("idempotency-key");
    if (key && !/^[A-Za-z0-9_-]{1,80}$/.test(key)) {
      return Response.json({ detail: "Invalid idempotency key" }, { status: 422 });
    }
    if (key) headers["Idempotency-Key"] = key;
  }
  const timeoutMs = target.startsWith("/v1/creative") ? CREATIVE_TIMEOUT_MS : DEFAULT_TIMEOUT_MS;
  try {
    const response = await fetch(`${videoApiBase()}${target}`, {
      method, headers, body, cache: "no-store", signal: AbortSignal.timeout(timeoutMs),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ detail: "Video API unavailable" }, { status: 502 });
  }
}

export async function GET(request: Request, context: Context) { return proxy(request, context, "GET"); }
export async function POST(request: Request, context: Context) { return proxy(request, context, "POST"); }
