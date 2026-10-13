# Veyra frontend

Next.js frontend with Clerk sign-in and a server-side OAuth connection to the Python video API. See [docs/AUTH.md](../docs/AUTH.md) for the authorization-code + S256 PKCE flow, required server-side variables, and account ownership rules.

```powershell
cd frontend
npm install
npm run dev
```

Start the Python API separately on `http://127.0.0.1:8000`. Open `http://localhost:3000`, sign in, select **Connect video account**, then choose a model and generate a clip. Generation is billable. `npm run lint` and `npm run build` verify the frontend.

The `/mcp` page provides a downloadable local MCP client bundle, the agent skill, and a ready-to-use agent prompt. It reads `VIDEO_API_BASE_URL` from the frontend server environment when generating the connection example. Keep that variable set to the current API URL in `frontend/.env.local` for local development and update it to the deployed HTTPS URL when the API is deployed. The page never exposes an API token; users add their own private token to their MCP client settings. `npm run dev` and `npm run build` refresh the downloadable ZIP and prompt from the repository sources.

Set `NEXT_PUBLIC_SITE_URL` to the deployed HTTPS origin so Veyra's Open Graph and Twitter images use the correct absolute URL. Vercel deployments can use `VERCEL_URL` automatically.
