# Veyra frontend

Next.js frontend with a public marketing page and a signed-in `/app` video dashboard. The dashboard forwards the current Clerk session token to the Python API from server-side routes. The separate `/mcp` page documents the agent client flow. See [docs/AUTH.md](../docs/AUTH.md) for account ownership and token verification.

```powershell
cd frontend
npm install
npm run dev
```

Start the Python API separately on `http://127.0.0.1:8000`, with `CLERK_WEB_ORIGIN=http://localhost:3000`. Open `http://localhost:3000`, sign up or sign in, and the app opens `/app`. Choose a model and generate a clip from the dashboard. Generation is billable. `npm run lint` and `npm run build` verify the frontend.

The `/mcp` page shows the hosted MCP endpoint, browser authorization flow, a copyable agent setup prompt, and a skill-only ZIP built from `.agent/skills/video-generation-mcp`. Set `MCP_PUBLIC_ORIGIN` on the Next.js server to the public origin of the hosted MCP process; the page displays `${MCP_PUBLIC_ORIGIN}/mcp`. It does not expose or require a private API token. The dashboard still uses `VIDEO_API_BASE_URL` server-side to reach the Python API. See [hosted MCP setup](../docs/MCP_SERVER.md) for deployment and OAuth configuration.

Set `NEXT_PUBLIC_SITE_URL` to the deployed HTTPS origin so Veyra's Open Graph and Twitter images use the correct absolute URL. Vercel deployments can use `VERCEL_URL` automatically.
