import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { userId, redirectToSignIn } = await auth();
  if (!userId) return redirectToSignIn({ returnBackUrl: request.url });

  const incoming = new URL(request.url);
  const issuer = process.env.CLERK_OAUTH_ISSUER;
  const clientId = process.env.CLERK_OAUTH_CLIENT_ID;
  const mcpOrigin = process.env.MCP_PUBLIC_ORIGIN?.replace(/\/$/, "");
  if (!issuer || !clientId || !mcpOrigin) {
    return NextResponse.json({ detail: "MCP authorization is not configured" }, { status: 503 });
  }
  if (incoming.searchParams.get("client_id") !== clientId ||
      incoming.searchParams.get("redirect_uri") !== `${mcpOrigin}/auth/callback`) {
    return NextResponse.json({ detail: "Invalid MCP authorization request" }, { status: 400 });
  }
  const upstream = new URL("/oauth/authorize", issuer);
  upstream.search = incoming.search;
  return NextResponse.redirect(upstream);
}
