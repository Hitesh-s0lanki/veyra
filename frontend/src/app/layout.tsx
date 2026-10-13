import {
  ClerkProvider,
  Show,
  SignInButton,
  SignUpButton,
  UserButton,
} from "@clerk/nextjs";
import { shadcn } from "@clerk/ui/themes";
import type { Metadata, Viewport } from "next";
import { Manrope, Space_Grotesk, Geist_Mono } from "next/font/google";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";
import { buttonVariants } from "@/components/ui/button";
import { SiteFooter } from "@/components/site-footer";
import "./globals.css";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ??
      (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000"),
  ),
  title: { default: "Veyra — AI Video Generator", template: "%s | Veyra" },
  description: "Imagine it. See it move. Turn text and images into cinematic AI videos with Veyra.",
  applicationName: "Veyra",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [{ url: "/favicon.ico", sizes: "any" }, { url: "/icon.png", type: "image/png" }],
    apple: [{ url: "/apple-icon.png", sizes: "180x180" }],
  },
  openGraph: {
    type: "website",
    title: "Veyra — Imagine it. See it move.",
    description: "Turn text and images into cinematic AI videos.",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Veyra AI Video Generator" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Veyra — AI Video Generator",
    images: ["/og-image.png"],
  },
};

export const viewport: Viewport = { themeColor: "#090F29" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${manrope.className} ${manrope.variable} ${spaceGrotesk.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col font-sans" style={{ overflowX: "clip" }}>
        <ClerkProvider appearance={{ theme: shadcn }}>
          <header className="border-b border-[#e9e8e3] bg-[#f8f8f5]">
            <nav className="mx-auto flex w-full max-w-[1500px] items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-10" aria-label="Main navigation">
              <Link href="/" className="inline-flex shrink-0 items-center rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4" aria-label="Veyra home">
                <Image src="/veyra-logo.png" alt="Veyra — Imagine it. See it move." width={1200} height={470} priority className="h-auto w-32 sm:w-40" />
              </Link>
              <div className="hidden items-center gap-2 text-sm font-semibold text-[#525650] md:flex">
                <Link href="/#showcase" className="rounded-full px-4 py-2.5 transition hover:bg-[#e9ece3] hover:text-[#191a1e] focus-visible:outline-2">Explore</Link>
                <Link href="/#how-it-works" className="rounded-full px-4 py-2.5 transition hover:bg-[#e9ece3] hover:text-[#191a1e] focus-visible:outline-2">How it works</Link>
                <Link href="/#create" className="rounded-full px-4 py-2.5 transition hover:bg-[#e9ece3] hover:text-[#191a1e] focus-visible:outline-2">Studio</Link>
                <Link href="/mcp" className="rounded-full px-4 py-2.5 transition hover:bg-[#e9ece3] hover:text-[#191a1e] focus-visible:outline-2">MCP</Link>
              </div>
              <div className="flex items-center gap-2">
                <Suspense fallback={<span className="text-sm text-muted-foreground">Loading account...</span>}>
                  <Show when="signed-out">
                    <SignInButton mode="modal">
                      <button className={`${buttonVariants({ variant: "outline" })} min-h-10 rounded-full px-4 font-semibold`}>
                        Sign in
                      </button>
                    </SignInButton>
                    <SignUpButton mode="modal">
                      <button className={`${buttonVariants()} min-h-10 rounded-full px-4 font-semibold`}>Sign up</button>
                    </SignUpButton>
                  </Show>
                  <Show when="signed-in">
                    <UserButton />
                  </Show>
                </Suspense>
              </div>
            </nav>
            <div className="flex items-center gap-5 border-t border-[#e9e8e3] px-4 py-1 text-sm font-semibold text-[#525650] md:hidden">
              <Link href="/#showcase" className="inline-flex min-h-10 items-center">Explore</Link>
              <Link href="/#create" className="inline-flex min-h-10 items-center">Studio</Link>
              <Link href="/mcp" className="inline-flex min-h-10 items-center">MCP</Link>
            </div>
          </header>
          {children}
          <SiteFooter />
        </ClerkProvider>
      </body>
    </html>
  );
}
