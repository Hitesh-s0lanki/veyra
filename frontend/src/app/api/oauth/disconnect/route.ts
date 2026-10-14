import { disconnect, sameOrigin } from "@/lib/video-oauth";

export async function POST(request: Request) {
  if (!sameOrigin(request)) return Response.json({ detail: "Invalid origin" }, { status: 403 });
  try {
    await disconnect();
    return Response.json({ connected: false });
  } catch {
    return Response.json({ detail: "Could not disconnect video account" }, { status: 502 });
  }
}
