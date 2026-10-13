import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Blocks, ShieldCheck, Terminal } from "lucide-react";
import { McpSetupActions } from "@/components/mcp-setup-actions";

export const metadata: Metadata = {
  title: "Connect an agent",
  description: "Download the Video Generation MCP client, skill, and agent prompt.",
};

export default function McpPage() {
  const apiUrl = process.env.VIDEO_API_BASE_URL || "http://127.0.0.1:8000";

  return <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
    <Link href="/" className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-[#5e625a] hover:text-[#191a1e] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6b8440]">
      <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to studio
    </Link>
    <div className="mt-8 overflow-hidden rounded-[2rem] bg-[#1c1d22] px-6 py-10 text-white sm:px-10 sm:py-12">
      <div className="grid items-end gap-8 md:grid-cols-[1.4fr_0.8fr]">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-[#9ebc6e]/40 bg-[#c9e69b]/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-[#d8efb1]">
            <Blocks className="h-3.5 w-3.5" aria-hidden="true" /> Agent connection
          </p>
          <h1 className="mt-5 max-w-2xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">Bring video generation into your agent.</h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-[#c4c7c0]">Connect the local MCP client, install the video skill, and give your agent a prompt that covers the complete workflow.</p>
        </div>
        <div className="grid gap-3 text-sm text-[#dce9c7]">
          <p className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3"><Terminal className="h-5 w-5 shrink-0" aria-hidden="true" /> Seven purpose-built MCP tools</p>
          <p className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3"><ShieldCheck className="h-5 w-5 shrink-0" aria-hidden="true" /> Token stays in your MCP client</p>
        </div>
      </div>
    </div>
    <div className="mt-8"><McpSetupActions apiUrl={apiUrl} /></div>
  </main>;
}
