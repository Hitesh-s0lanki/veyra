import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { completeAuthorization } from "@/lib/video-oauth";

export async function GET(request: Request) {
  const { userId } = await auth();
  const url = new URL(request.url);
  if (!userId || url.searchParams.has("error") || !url.searchParams.get("code") || !url.searchParams.get("state")) {
    return NextResponse.redirect(new URL("/app?connection=failed", process.env.APP_ORIGIN ?? "http://localhost:3000"));
  }
  try {
    await completeAuthorization(url.searchParams.get("code")!, url.searchParams.get("state")!, userId);
    return NextResponse.redirect(new URL("/app?connection=success", process.env.APP_ORIGIN ?? "http://localhost:3000"));
  } catch {
    return NextResponse.redirect(new URL("/app?connection=failed", process.env.APP_ORIGIN ?? "http://localhost:3000"));
  }
}
