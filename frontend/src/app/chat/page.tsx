import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { VideoDashboard } from "@/components/video-dashboard";

export default function ChatPage(props: PageProps<"/chat">) {
  return <Suspense fallback={<main className="p-8 text-sm text-muted-foreground">Opening chat…</main>}><AuthenticatedChat {...props} /></Suspense>;
}

async function AuthenticatedChat({ searchParams }: PageProps<"/chat">) {
  const id = (await searchParams).id;
  const returnBackUrl = typeof id === "string" ? `/chat?id=${encodeURIComponent(id)}` : "/chat";
  const { userId, redirectToSignIn } = await auth();
  if (!userId) return redirectToSignIn({ returnBackUrl });
  if (typeof id !== "string" || !/^con_[a-f0-9]{32}$/.test(id)) redirect("/app?mode=concept");
  return <VideoDashboard />;
}
