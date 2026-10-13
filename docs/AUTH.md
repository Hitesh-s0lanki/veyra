# Clerk account connection and video API authentication

The Next.js frontend and Python video API use one Clerk OAuth application. The frontend is a confidential OAuth client: it sends the user through Clerk's authorization-code flow with a fresh S256 PKCE challenge and state value. The callback exchanges the code on the Next.js server, checks the token's Clerk subject against the signed-in Clerk user, and stores access and refresh tokens in an encrypted HttpOnly cookie. The browser calls same-origin Next.js routes; those routes forward the OAuth access token to the Python API. The API introspects each token with Clerk and accepts it only when it is active, belongs to the configured client, includes `profile`, and has a valid Clerk user subject. Jobs and assets remain scoped to that subject.

This repository's local Clerk development instance has a dedicated OAuth application with PKCE required and callback `http://localhost:3000/api/oauth/callback`. Its client credentials are in the ignored `frontend/.env.local` and root `.env` files. They must be configured separately for each deployed environment. Do not put the client secret, cookie secret, refresh token, or API bearer token in `NEXT_PUBLIC_` variables.

## Configuration

In the [Clerk OAuth applications dashboard](https://dashboard.clerk.com/~/oauth-applications), create a confidential application with `profile offline_access` scopes, enable **Require PKCE**, and add the exact frontend callback URL. Keep the consent screen enabled. Set the following on the **Next.js server**:

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

## Request flow

1. User signs into the frontend with Clerk and selects **Connect video account**.
2. `/api/oauth/start` writes a short-lived encrypted, HttpOnly state and code verifier cookie, then redirects to Clerk with `code_challenge_method=S256`.
3. Clerk authenticates the user and obtains consent. `/api/oauth/callback` checks state, exchanges the code with its verifier and client secret, and checks the access token's subject against the current Clerk session.
4. The frontend calls `/api/video/models`, `/api/video/videos`, status, download, cancel, or `/api/video/assets/upload` on the same origin. Next.js attaches the access token server-side. The Python API verifies the token with Clerk and uses its subject as the owner ID.
5. The frontend refreshes expired access tokens using the encrypted refresh token and verifies the subject again. **Disconnect account** revokes the refresh token and clears the local cookie.

The video API does not trust a browser-supplied user ID. OAuth token validation happens on each API call so revocation and expiry take effect without waiting for a local cache. Status and output URLs remain owner-scoped. Signed MP4 URLs last one hour. Generating a video starts a billable Modal job; account connection and model listing do not.

Clerk's [PKCE guidance](https://clerk.com/docs/guides/configure/auth-strategies/oauth/how-clerk-implements-oauth) and [token introspection guide](https://clerk.com/docs/guides/configure/auth-strategies/oauth/single-sign-on) describe the provider behavior used here.
