# Clerk authentication for the dashboard and integrations

The web dashboard lives at `/app`. A user signs in with Clerk, and the Next.js
server forwards the current short-lived Clerk session token to the Python video
API. The API checks the JWT signature against Clerk's JWKS, then verifies its
issuer, expiry, session ID, user ID, and authorized frontend origin. Set
`CLERK_WEB_ORIGIN` on the API host to the exact frontend origin, such as
`http://localhost:3000` or the production HTTPS origin. The browser never
receives a static API token. New users can open the dashboard immediately after
signup; they do not need to connect an OAuth account.

The hosted MCP server uses the configured Clerk OAuth application. An MCP client
connects to its remote URL, opens browser sign-in and consent, and receives a
client-specific token. The hosted server validates the upstream Clerk token and
uses it for the video API. The local stdio MCP server retains its private API
token workflow. The dashboard does not invoke either MCP flow.

## Optional OAuth integration

The repository also has a confidential Clerk OAuth client. An integration can send a user through Clerk's authorization-code flow with a fresh S256 PKCE challenge and state value. The callback exchanges the code on the Next.js server, checks the token's Clerk subject against the signed-in Clerk user, and stores access and refresh tokens in an encrypted HttpOnly cookie. The API introspects OAuth tokens with Clerk and accepts them only when active, issued to the configured client, and granted the `profile` scope. Jobs and assets remain scoped to the verified subject.

This repository's local Clerk development instance has a dedicated OAuth application with PKCE required and callback `http://localhost:3000/api/oauth/callback`. Its client credentials are in the ignored `frontend/.env.local` and root `.env` files. They must be configured separately for each deployed environment. Do not put the client secret, cookie secret, refresh token, or API bearer token in `NEXT_PUBLIC_` variables.

## Configuration

For the dashboard, set `APP_ORIGIN` and `VIDEO_API_BASE_URL` on the Next.js server, and `CLERK_OAUTH_ISSUER` plus `CLERK_WEB_ORIGIN` on the Python API. The API verifies session tokens with Clerk's JWKS. No OAuth client or cookie secret is needed for the dashboard.

For the optional OAuth integration, create a confidential application in the [Clerk OAuth applications dashboard](https://dashboard.clerk.com/~/oauth-applications) with `profile offline_access` scopes, enable **Require PKCE**, and add the exact frontend callback URL. Keep the consent screen enabled. Set the following on the **Next.js server**:

```text
APP_ORIGIN=http://localhost:3000
VIDEO_API_BASE_URL=http://127.0.0.1:8000
CLERK_OAUTH_ISSUER=https://your-instance.clerk.accounts.dev
CLERK_OAUTH_CLIENT_ID=<client-id>
CLERK_OAUTH_CLIENT_SECRET=<client-secret>
OAUTH_COOKIE_SECRET=<64 hex characters from 32 random bytes>
```

Set the same `CLERK_OAUTH_ISSUER`, `CLERK_OAUTH_CLIENT_ID`, and `CLERK_OAUTH_CLIENT_SECRET` on the **Python API**. Generate `OAUTH_COOKIE_SECRET` once and keep it stable across frontend replicas and restarts; rotating it disconnects existing browsers. Production `APP_ORIGIN` and remote API URLs must use HTTPS. The callback URL registered in Clerk must exactly match `${APP_ORIGIN}/api/oauth/callback`.

The API can also keep `API_TOKENS_JSON` for non-browser integrations. The frontend never uses a static API token. Browser calls to the API go through Next.js route handlers, so API CORS access is unnecessary for this frontend. If another browser client must call the API directly, set `CORS_ORIGINS` to its explicit origin.

## Optional OAuth request flow

1. An integration starts `/api/oauth/start` for a signed-in user.
2. `/api/oauth/start` writes a short-lived encrypted, HttpOnly state and code verifier cookie, then redirects to Clerk with `code_challenge_method=S256`.
3. Clerk authenticates the user and obtains consent. `/api/oauth/callback` checks state, exchanges the code with its verifier and client secret, and checks the access token's subject against the current Clerk session.
4. The integration can use the access token with the Python API. The API verifies the token with Clerk and uses its subject as the owner ID.
5. The server can refresh expired access tokens using the encrypted refresh token. `/api/oauth/disconnect` revokes the refresh token and clears the local cookie.

The video API does not trust a browser-supplied user ID. OAuth token validation happens on each API call so revocation and expiry take effect without waiting for a local cache. Status and output URLs remain owner-scoped. Signed MP4 URLs last one hour. Generating a video starts a billable Modal job; account connection and model listing do not.

Clerk's [PKCE guidance](https://clerk.com/docs/guides/configure/auth-strategies/oauth/how-clerk-implements-oauth) and [token introspection guide](https://clerk.com/docs/guides/configure/auth-strategies/oauth/single-sign-on) describe the provider behavior used here.
