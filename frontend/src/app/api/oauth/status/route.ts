import { auth } from "@clerk/nextjs/server";
import { accessTokenForCurrentUser } from "@/lib/video-oauth";

export async function GET() {
  const { userId } = await auth();
  if (!userId) return Response.json({ connected: false }, { status: 401 });
  return Response.json({ connected: Boolean(await accessTokenForCurrentUser()) });
}
