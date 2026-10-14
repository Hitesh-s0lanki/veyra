import { auth } from "@clerk/nextjs/server";
import { Suspense } from "react";
import { VideoDashboard } from "@/components/video-dashboard";

async function AuthenticatedDashboard({ searchParams }: { searchParams: PageProps<"/app">["searchParams"] }) {
  const video = (await searchParams).video;
  const returnBackUrl = typeof video === "string" ? `/app?video=${encodeURIComponent(video)}` : "/app";
  const { userId, redirectToSignIn } = await auth();
  if (!userId) return redirectToSignIn({ returnBackUrl });
  return <VideoDashboard />;
}

export default function DashboardPage({ searchParams }: PageProps<"/app">) {
  return <Suspense fallback={<main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-10 text-sm text-muted-foreground">Loading your dashboard…</main>}>
    <AuthenticatedDashboard searchParams={searchParams} />
  </Suspense>;
}
