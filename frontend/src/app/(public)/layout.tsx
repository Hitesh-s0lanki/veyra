import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";
import { SiteFooter } from "@/components/site-footer";
import { buttonVariants } from "@/components/ui/button";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header className="border-b border-[#e9e8e3] bg-[#f8f8f5]">
        <nav className="mx-auto flex w-full max-w-[1500px] flex-wrap items-center justify-between gap-2 px-4 py-2 sm:gap-3 sm:px-6 sm:py-2.5 lg:px-10" aria-label="Main navigation">
          <Link href="/" className="inline-flex shrink-0 items-center rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4" aria-label="Veyra home">
            <Image src="/veyra-logo.png" alt="Veyra — Imagine it. See it move." width={1200} height={470} priority className="h-auto w-20 sm:w-28 lg:w-32" />
          </Link>
          <div className="hidden items-center gap-1 text-[13px] font-semibold text-[#525650] md:flex">
            <Link href="/#showcase" className="rounded-full px-3 py-2 transition hover:bg-[#e9ece3] hover:text-[#191a1e] focus-visible:outline-2">Explore</Link>
            <Link href="/#how-it-works" className="rounded-full px-3 py-2 transition hover:bg-[#e9ece3] hover:text-[#191a1e] focus-visible:outline-2">How it works</Link>
            <Link href="/mcp" className="rounded-full px-3 py-2 transition hover:bg-[#e9ece3] hover:text-[#191a1e] focus-visible:outline-2">MCP</Link>
          </div>
          <div className="flex items-center gap-2">
            <Suspense fallback={<span className="text-sm text-muted-foreground">Loading account...</span>}>
              <Show when="signed-out">
                <SignInButton mode="modal">
                  <button className={`${buttonVariants({ variant: "outline" })} min-h-10 rounded-full px-3 font-semibold sm:px-4`}>
                    Sign in
                  </button>
                </SignInButton>
                <SignUpButton mode="modal">
                  <button className={`${buttonVariants()} min-h-10 rounded-full px-3 font-semibold sm:px-4`}>Sign up</button>
                </SignUpButton>
              </Show>
              <Show when="signed-in">
                <Link href="/app" className="inline-flex min-h-9 items-center rounded-full bg-[#e9ece3] px-3 text-[13px] font-semibold text-[#191a1e] transition hover:bg-[#dfe4d8] focus-visible:outline-2 focus-visible:outline-offset-2">Dashboard</Link>
                <UserButton />
              </Show>
            </Suspense>
          </div>
        </nav>
        <nav className="flex flex-wrap items-center gap-x-4 border-t border-[#e9e8e3] px-4 py-0.5 text-[13px] font-semibold text-[#525650] md:hidden" aria-label="Mobile navigation">
          <Link href="/#showcase" className="inline-flex min-h-9 items-center">Explore</Link>
          <Link href="/#how-it-works" className="inline-flex min-h-9 items-center">How it works</Link>
          <Link href="/mcp" className="inline-flex min-h-9 items-center">MCP</Link>
        </nav>
      </header>
      {children}
      <SiteFooter />
    </>
  );
}
