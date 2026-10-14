import { auth } from "@clerk/nextjs/server";
import { Suspense } from "react";
import { redirect } from "next/navigation";
import { VideoDashboard } from "@/components/video-dashboard";

async function AuthenticatedDashboard({ searchParams }: { searchParams: PageProps<"/app">["searchParams"] }) {
  const params = await searchParams;
  const video = params.video;
  const returnBackUrl = typeof video === "string" ? `/app?video=${encodeURIComponent(video)}` : typeof params.concept === "string" ? `/app?concept=${encodeURIComponent(params.concept)}` : "/app";
  const { userId, redirectToSignIn } = await auth();
  if (!userId) return redirectToSignIn({ returnBackUrl });
  if (params.mode === "concept" && typeof params.concept === "string") redirect(`/chat?id=${encodeURIComponent(params.concept)}`);
  return <VideoDashboard />;
}

export default function DashboardPage({ searchParams }: PageProps<"/app">) {
  return <Suspense fallback={<main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-10 text-sm text-muted-foreground">Loading your dashboard…</main>}>
    <AuthenticatedDashboard searchParams={searchParams} />
  </Suspense>;
}
