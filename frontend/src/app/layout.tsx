import { ClerkProvider } from "@clerk/nextjs";
import { shadcn } from "@clerk/ui/themes";
import type { Metadata, Viewport } from "next";
import { Manrope, Space_Grotesk, Geist_Mono } from "next/font/google";
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
        <ClerkProvider appearance={{ theme: shadcn }} signUpForceRedirectUrl="/app" signInForceRedirectUrl="/app">
          {children}
        </ClerkProvider>
      </body>
    </html>
  );
}
