import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { startAuthorization } from "@/lib/video-oauth";

export async function GET() {
  const { userId } = await auth();
  if (!userId) return NextResponse.redirect(new URL("/sign-in", process.env.APP_ORIGIN ?? "http://localhost:3000"));
  try {
    return NextResponse.redirect(await startAuthorization(userId));
  } catch {
    return NextResponse.json({ detail: "OAuth connection is not configured" }, { status: 503 });
  }
}
