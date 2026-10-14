import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { Suspense } from "react";

export default function ConceptsPage(props: PageProps<"/app/concepts">) {
  return <Suspense fallback={<main className="p-8 text-sm text-muted-foreground">Opening your concept…</main>}><ConceptRedirect {...props} /></Suspense>;
}

async function ConceptRedirect({ searchParams }: PageProps<"/app/concepts">) {
  const { userId, redirectToSignIn } = await auth();
  if (!userId) return redirectToSignIn({ returnBackUrl: "/app/concepts" });
  const concept = (await searchParams).concept;
  redirect(typeof concept === "string" ? `/chat?id=${encodeURIComponent(concept)}` : "/app?mode=concept");
}
