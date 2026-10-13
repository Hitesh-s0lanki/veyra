"use client";

import { useState } from "react";
import { Copy, Download, ExternalLink } from "lucide-react";

const skillRepositoryUrl = "https://github.com/Hitesh-s0lanki/video-generation-pipeline/tree/dev/.agent/skills/video-generation-mcp";
const skillFileUrl = "https://raw.githubusercontent.com/Hitesh-s0lanki/video-generation-pipeline/dev/.agent/skills/video-generation-mcp/SKILL.md";
const promptingFileUrl = "https://raw.githubusercontent.com/Hitesh-s0lanki/video-generation-pipeline/dev/.agent/skills/video-generation-mcp/references/prompting.md";

export function McpSetupActions({ mcpUrl }: { mcpUrl: string | null }) {
  const [feedback, setFeedback] = useState("");
  const config = mcpUrl ? JSON.stringify({ mcpServers: { "video-generation": { url: mcpUrl } } }, null, 2) : null;
  const agentPrompt = mcpUrl ? `Connect this agent to the Video Generation remote MCP server at ${mcpUrl} using your MCP client's HTTP connection and browser OAuth sign-in. If you cannot change MCP settings yourself, give me the exact steps and configuration to add this URL. Do not ask me for an API token.

Install the video-generation-mcp skill from this repository, preserving its folder structure:
${skillFileUrl}
${promptingFileUrl}
Put SKILL.md in a video-generation-mcp folder and prompting.md in its references folder. If you cannot install skills, read both files and follow them for this conversation.

After connecting, discover the available MCP tools and call list_video_models to confirm access. This hosted server provides list_video_models, generate_video, get_video_status, get_video_url, and cancel_video. Use only tools that are actually available. Do not call generate_video until I explicitly ask you to create a clip; it uses credits. For a completed video, use get_video_url to return a one-hour link. Report the connection result and available models.` : null;

  async function copy(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      setFeedback(`${label} copied`);
    } catch {
      setFeedback(`Could not copy ${label.toLowerCase()}. Select the text and copy it manually.`);
    }
  }

  return <div className="space-y-7">
    <section className="rounded-3xl border border-[#e7e9e1] bg-white p-5 shadow-sm sm:p-7" aria-labelledby="connect-title">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6b8440]">01 / Connect</p>
      <h2 id="connect-title" className="mt-2 text-2xl font-semibold tracking-tight text-[#191a1e]">Add the hosted MCP URL</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#5e625a]">Add this URL as a remote HTTP MCP server in your agent client. No local Python setup or API token is needed.</p>
      {mcpUrl ? <>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <code className="min-w-0 flex-1 break-all rounded-2xl bg-[#f1f2ed] px-4 py-3 text-sm text-[#191a1e]">{mcpUrl}</code>
          <button type="button" onClick={() => void copy(mcpUrl, "MCP URL")} className="inline-flex min-h-11 items-center gap-2 rounded-full border border-[#d8ded0] px-4 text-sm font-semibold text-[#252923] hover:bg-[#f5f6f0] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6b8440]"><Copy className="h-4 w-4" aria-hidden="true" /> Copy URL</button>
        </div>
        <p className="mt-4 text-sm leading-6 text-[#5e625a]">If your client accepts JSON MCP settings, use this example:</p>
        <div className="mt-3 flex justify-end"><button type="button" onClick={() => void copy(config!, "MCP configuration")} className="inline-flex min-h-11 items-center gap-2 rounded-full border border-[#d8ded0] px-4 text-sm font-semibold text-[#252923] hover:bg-[#f5f6f0] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6b8440]"><Copy className="h-4 w-4" aria-hidden="true" /> Copy config</button></div>
        <pre className="mt-3 overflow-x-auto rounded-2xl bg-[#1c1d22] p-5 text-xs leading-6 text-[#dce9c7] sm:text-sm"><code>{config}</code></pre>
      </> : <p className="mt-5 rounded-2xl bg-[#f1f2ed] px-4 py-3 text-sm text-[#5e625a]">The hosted MCP URL will appear here when the service is deployed.</p>}
    </section>

    <section className="rounded-3xl border border-[#e7e9e1] bg-white p-5 shadow-sm sm:p-7" aria-labelledby="auth-title">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6b8440]">02 / Authorize</p>
      <h2 id="auth-title" className="mt-2 text-2xl font-semibold tracking-tight text-[#191a1e]">Sign in when prompted</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#5e625a]">Your MCP client opens a browser to authorize the connection. Sign in with your video generation account and approve access. The client then receives its own connection token and can use your account’s video tools. You do not need to paste a token into the client or an agent prompt.</p>
    </section>

    <section className="rounded-3xl border border-[#e7e9e1] bg-white p-5 shadow-sm sm:p-7" aria-labelledby="prompt-title">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6b8440]">03 / Agent prompt</p>
      <h2 id="prompt-title" className="mt-2 text-2xl font-semibold tracking-tight text-[#191a1e]">Give your agent the setup prompt</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#5e625a]">Copy this into your agent chat. It tells the agent to connect to this MCP URL, install the <a href={skillRepositoryUrl} target="_blank" rel="noreferrer" className="font-medium text-[#426222] underline underline-offset-2">skill from this repository</a>, sign in through the browser, and verify the tools with a model list.</p>
      {agentPrompt ? <>
        <div className="mt-4 flex flex-wrap justify-end gap-3">
          <a href="/downloads/video-generation-mcp-skill.zip" download className="inline-flex min-h-11 items-center gap-2 rounded-full border border-[#d8ded0] px-5 text-sm font-semibold text-[#252923] hover:bg-[#f5f6f0] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6b8440]"><Download className="h-4 w-4" aria-hidden="true" /> Download skill</a>
          <button type="button" onClick={() => void copy(agentPrompt, "Agent prompt")} className="inline-flex min-h-11 items-center gap-2 rounded-full bg-[#d8efb1] px-5 text-sm font-semibold text-[#243020] hover:bg-[#c9e69b] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6b8440]"><Copy className="h-4 w-4" aria-hidden="true" /> Copy agent prompt</button>
        </div>
        <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-[#1c1d22] p-5 text-xs leading-6 text-[#dce9c7] sm:text-sm"><code>{agentPrompt}</code></pre>
      </> : <p className="mt-4 rounded-2xl bg-[#f1f2ed] px-4 py-3 text-sm text-[#5e625a]">The prompt will appear when the hosted MCP URL is configured.</p>}
    </section>

    <section className="rounded-3xl border border-[#e7e9e1] bg-white p-5 shadow-sm sm:p-7" aria-labelledby="use-title">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6b8440]">04 / Use</p>
      <h2 id="use-title" className="mt-2 text-2xl font-semibold tracking-tight text-[#191a1e]">Ask your agent to make a video</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#5e625a]">Start with <code className="rounded bg-[#f1f2ed] px-1">list_video_models</code>, then use <code className="rounded bg-[#f1f2ed] px-1">generate_video</code> and <code className="rounded bg-[#f1f2ed] px-1">get_video_status</code>. After completion, <code className="rounded bg-[#f1f2ed] px-1">get_video_url</code> returns a one-hour download link. Generation uses credits; listing models does not.</p>
      <a href="/app" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-full bg-[#d8efb1] px-5 text-sm font-semibold text-[#243020] hover:bg-[#c9e69b] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6b8440]">View your account <ExternalLink className="h-4 w-4" aria-hidden="true" /></a>
    </section>
    <p role="status" aria-live="polite" className="min-h-5 text-sm font-medium text-[#526b32]">{feedback}</p>
  </div>;
}
