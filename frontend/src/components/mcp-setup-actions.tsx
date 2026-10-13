"use client";

import { useState } from "react";
import { Copy, Download } from "lucide-react";

type Platform = "windows" | "unix";

export function McpSetupActions({ apiUrl }: { apiUrl: string }) {
  const [platform, setPlatform] = useState<Platform>("windows");
  const [feedback, setFeedback] = useState("");
  const python = platform === "windows"
    ? "C:\\path\\to\\video-generation-agent-kit\\.venv\\Scripts\\python.exe"
    : "/absolute/path/to/video-generation-agent-kit/.venv/bin/python";
  const launcher = platform === "windows"
    ? "C:\\path\\to\\video-generation-agent-kit\\mcp_server.py"
    : "/absolute/path/to/video-generation-agent-kit/mcp_server.py";
  const config = JSON.stringify({
    mcpServers: {
      "video-generation": {
        command: python,
        args: [launcher],
        env: {
          VIDEO_API_BASE_URL: apiUrl,
          VIDEO_API_TOKEN: "<your-private-api-token>",
        },
      },
    },
  }, null, 2);

  async function copy(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      setFeedback(`${label} copied`);
    } catch {
      setFeedback(`Could not copy ${label.toLowerCase()}. Select the text and copy it manually.`);
    }
  }

  async function copyPrompt() {
    try {
      const response = await fetch("/downloads/AGENT_PROMPT.md");
      if (!response.ok) throw new Error("Prompt unavailable");
      await copy(await response.text(), "Agent prompt");
    } catch {
      setFeedback("Could not load the prompt. Use the download link instead.");
    }
  }

  return <div className="space-y-7">
    <section className="rounded-3xl border border-[#e7e9e1] bg-white p-5 shadow-sm sm:p-7" aria-labelledby="download-title">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="max-w-xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6b8440]">01 / Download</p>
          <h2 id="download-title" className="mt-2 text-2xl font-semibold tracking-tight text-[#191a1e]">Get the agent kit</h2>
          <p className="mt-2 text-sm leading-6 text-[#5e625a]">The ZIP includes the local MCP launcher, its Python dependencies list, the installable video skill, prompt guidance, and a setup guide.</p>
        </div>
        <a href="/downloads/video-generation-agent-kit.zip" download
          className="inline-flex min-h-11 items-center gap-2 rounded-full bg-[#1c1d22] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#35383e] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6b8440]">
          <Download className="h-4 w-4" aria-hidden="true" /> Download agent kit
        </a>
      </div>
      <div className="mt-6 grid gap-3 border-t border-[#e7e9e1] pt-5 text-sm text-[#555b51] sm:grid-cols-3">
        <span><strong className="block text-[#191a1e]">MCP client</strong>Seven video tools</span>
        <span><strong className="block text-[#191a1e]">Agent skill</strong>Tool workflow + model prompts</span>
        <span><strong className="block text-[#191a1e]">Setup guide</strong>Windows, macOS, and Linux</span>
      </div>
    </section>

    <section className="rounded-3xl border border-[#e7e9e1] bg-white p-5 shadow-sm sm:p-7" aria-labelledby="config-title">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6b8440]">02 / Connect</p>
      <h2 id="config-title" className="mt-2 text-2xl font-semibold tracking-tight text-[#191a1e]">Add the MCP server</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#5e625a]">Extract the kit, create a Python virtual environment, and install <code className="rounded bg-[#f1f2ed] px-1">requirements-mcp.txt</code>. Replace both example paths and the token below, then paste the JSON into your MCP client settings.</p>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-full border border-[#e0e4d8] bg-[#f5f6f0] p-1" aria-label="Operating system">
          {(["windows", "unix"] as const).map((item) => <button key={item} type="button" onClick={() => setPlatform(item)} aria-pressed={platform === item}
            className={`min-h-10 rounded-full px-4 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6b8440] ${platform === item ? "bg-white text-[#191a1e] shadow-sm" : "text-[#62675c] hover:text-[#191a1e]"}`}>
            {item === "windows" ? "Windows" : "macOS / Linux"}
          </button>)}
        </div>
        <button type="button" onClick={() => void copy(config, "MCP configuration")}
          className="inline-flex min-h-11 items-center gap-2 rounded-full border border-[#d8ded0] px-4 text-sm font-semibold text-[#252923] hover:bg-[#f5f6f0] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6b8440]">
          <Copy className="h-4 w-4" aria-hidden="true" /> Copy config
        </button>
      </div>
      <pre className="mt-4 overflow-x-auto rounded-2xl bg-[#1c1d22] p-5 text-xs leading-6 text-[#dce9c7] sm:text-sm"><code>{config}</code></pre>
      <p className="mt-4 text-sm leading-6 text-[#5e625a]">The API URL is read from this site’s server configuration. It currently points to <code className="break-all rounded bg-[#f1f2ed] px-1">{apiUrl}</code>. If you run the MCP client on another machine while this is localhost, update <code>VIDEO_API_BASE_URL</code> to the deployed HTTPS API URL when available.</p>
      <p className="mt-2 text-sm leading-6 text-[#5e625a]">Your website sign-in is separate from MCP authentication. Obtain a private API token from the service administrator and place it only in your MCP client’s secret settings. Never paste it into a public prompt.</p>
    </section>

    <section className="rounded-3xl border border-[#e7e9e1] bg-white p-5 shadow-sm sm:p-7" aria-labelledby="prompt-title">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6b8440]">03 / Instruct</p>
      <h2 id="prompt-title" className="mt-2 text-2xl font-semibold tracking-tight text-[#191a1e]">Give your agent the full workflow</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#5e625a]">Install the kit’s <code>skills/video-generation-mcp</code> folder in your agent client. Then add this prompt as its initial instruction. It covers prompt-only requests, generation, image upload, polling, downloads, cancellation, costs, and token handling.</p>
      <div className="mt-5 flex flex-wrap gap-3">
        <a href="/downloads/AGENT_PROMPT.md" download className="inline-flex min-h-11 items-center gap-2 rounded-full bg-[#d8efb1] px-5 text-sm font-semibold text-[#243020] hover:bg-[#c9e69b] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6b8440]">
          <Download className="h-4 w-4" aria-hidden="true" /> Download agent prompt
        </a>
        <button type="button" onClick={() => void copyPrompt()} className="inline-flex min-h-11 items-center gap-2 rounded-full border border-[#d8ded0] px-5 text-sm font-semibold text-[#252923] hover:bg-[#f5f6f0] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6b8440]">
          <Copy className="h-4 w-4" aria-hidden="true" /> Copy prompt
        </button>
      </div>
      <p className="mt-4 text-sm text-[#5e625a]">Start by asking the agent to list available models. Creating a clip uses credits; prompt drafting and model discovery do not.</p>
    </section>
    <p role="status" aria-live="polite" className="min-h-5 text-sm font-medium text-[#526b32]">{feedback}</p>
  </div>;
}
