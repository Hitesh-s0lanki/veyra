// Single source of truth for the /api/video/* proxy whitelist.
// `scripts/check-video-routes.mjs` transpiles this file and verifies that every
// route the UI calls is mapped here, so a new client call cannot 404 silently.

export type ProxyMethod = "GET" | "POST" | "PUT";

export type RouteRule = {
  methods: ProxyMethod[];
  /** Literal segments or per-position regexes for validated IDs. */
  segments: (string | RegExp)[];
  /** Static backend path, or a builder receiving the regex-matched segments. */
  target: string | ((params: string[]) => string);
};

// IDs are produced by the API as a prefix plus 32 hex characters.
const JOB_ID = /^vid_[a-f0-9]{32}$/;
const ASSET_ID = /^asset_[a-f0-9]{32}$/;
const CONCEPT_ID = /^con_[a-f0-9]{32}$/;

export const VIDEO_API_ROUTES: RouteRule[] = [
  { methods: ["GET"], segments: ["models"], target: "/v1/models" },
  { methods: ["GET"], segments: ["wallet"], target: "/v1/wallet" },
  { methods: ["GET"], segments: ["wallet", "transactions"], target: "/v1/wallet/transactions" },
  { methods: ["GET"], segments: ["assets"], target: "/v1/assets" },
  { methods: ["GET"], segments: ["assets", ASSET_ID, "download"], target: (p) => `/v1/assets/${p[0]}/download` },
  { methods: ["GET", "POST"], segments: ["videos"], target: "/v1/videos" },
  { methods: ["POST"], segments: ["videos", "quote"], target: "/v1/videos/quote" },
  { methods: ["POST"], segments: ["videos", "url"], target: "/v1/videos/url" },
  { methods: ["GET"], segments: ["videos", JOB_ID], target: (p) => `/v1/videos/${p[0]}` },
  { methods: ["GET"], segments: ["videos", JOB_ID, "download"], target: (p) => `/v1/videos/${p[0]}/download` },
  { methods: ["POST"], segments: ["videos", JOB_ID, "cancel"], target: (p) => `/v1/videos/${p[0]}/cancel` },
  { methods: ["GET"], segments: ["creative", "pricing"], target: "/v1/creative/pricing" },
  { methods: ["POST"], segments: ["creative", "prompt"], target: "/v1/creative/prompt" },
  { methods: ["POST"], segments: ["creative", "images"], target: "/v1/creative/images" },
  { methods: ["GET", "POST"], segments: ["concepts"], target: "/v1/concepts" },
  { methods: ["GET"], segments: ["concepts", CONCEPT_ID], target: (p) => `/v1/concepts/${p[0]}` },
  { methods: ["POST"], segments: ["concepts", CONCEPT_ID, "chat"], target: (p) => `/v1/concepts/${p[0]}/chat` },
  { methods: ["PUT"], segments: ["concepts", CONCEPT_ID, "plan"], target: (p) => `/v1/concepts/${p[0]}/plan` },
  { methods: ["POST"], segments: ["concepts", CONCEPT_ID, "generate"], target: (p) => `/v1/concepts/${p[0]}/generate` },
  { methods: ["POST"], segments: ["concepts", CONCEPT_ID, "retry"], target: (p) => `/v1/concepts/${p[0]}/retry` },
];

export function matchVideoApiRoute(method: string, segments: string[]): string | null {
  for (const rule of VIDEO_API_ROUTES) {
    if (!rule.methods.includes(method as ProxyMethod)) continue;
    if (rule.segments.length !== segments.length) continue;
    const params: string[] = [];
    let matched = true;
    for (let index = 0; index < rule.segments.length; index += 1) {
      const expected = rule.segments[index];
      const actual = segments[index];
      if (typeof expected === "string") {
        if (expected !== actual) { matched = false; break; }
      } else {
        if (!expected.test(actual)) { matched = false; break; }
        params.push(actual);
      }
    }
    if (matched) return typeof rule.target === "string" ? rule.target : rule.target(params);
  }
  return null;
}
