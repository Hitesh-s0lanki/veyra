import type { Metadata } from "next";
import { Blocks, ShieldCheck, Terminal } from "lucide-react";
import { McpSetupActions } from "@/components/mcp-setup-actions";

export const metadata: Metadata = {
  title: "Connect an agent",
  description: "Connect your agent to the hosted Video Generation MCP server.",
};

export default function McpPage() {
  const origin = process.env.MCP_PUBLIC_ORIGIN?.replace(/\/$/, "");
  const mcpUrl = origin ? `${origin}/mcp` : null;

  return <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
    <div className="overflow-hidden rounded-[2rem] bg-[#1c1d22] px-6 py-10 text-white sm:px-10 sm:py-12">
      <div className="grid items-end gap-8 md:grid-cols-[1.4fr_0.8fr]">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-[#9ebc6e]/40 bg-[#c9e69b]/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-[#d8efb1]">
            <Blocks className="h-3.5 w-3.5" aria-hidden="true" /> Agent connection
          </p>
          <h1 className="mt-5 max-w-2xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">Bring video generation into your agent.</h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-[#c4c7c0]">Add the hosted MCP URL to your agent client, sign in with your account, and start using video tools.</p>
        </div>
        <div className="grid gap-3 text-sm text-[#dce9c7]">
          <p className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3"><Terminal className="h-5 w-5 shrink-0" aria-hidden="true" /> Hosted video tools</p>
          <p className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3"><ShieldCheck className="h-5 w-5 shrink-0" aria-hidden="true" /> Browser sign-in, no token to copy</p>
        </div>
      </div>
    </div>
    <div className="mt-8"><McpSetupActions mcpUrl={mcpUrl} /></div>
  </main>;
}
