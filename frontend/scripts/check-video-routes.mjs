// Verifies the /api/video/* proxy whitelist covers every route the UI calls.
// The table in src/lib/video-api-routes.ts is the single source of truth; this
// script transpiles it with the installed TypeScript package, then probes:
//   1. a fixed list of core method+path combinations (positive and negative),
//   2. every "/api/video/..." literal found in client source under src/app and
//      src/components, with ${...} segments probed using synthetic valid IDs.
// Run: npm run check:routes
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

const here = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(here, "..");
const libPath = join(frontendRoot, "src", "lib", "video-api-routes.ts");

// The dedicated upload route file handles this path; the catch-all never sees it.
const DEDICATED_ROUTES = new Set(["assets/upload"]);

const JOB_ID = `vid_${"a".repeat(32)}`;
const ASSET_ID = `asset_${"a".repeat(32)}`;

const METHOD_PROBES = [
  ["GET", ["models"], true],
  ["GET", ["wallet"], true],
  ["GET", ["wallet", "transactions"], true],
  ["GET", ["assets"], true],
  ["GET", ["assets", ASSET_ID, "download"], true],
  ["GET", ["videos"], true],
  ["POST", ["videos"], true],
  ["POST", ["videos", "quote"], true],
  ["POST", ["videos", "url"], true],
  ["GET", ["videos", JOB_ID], true],
  ["GET", ["videos", JOB_ID, "download"], true],
  ["POST", ["videos", JOB_ID, "cancel"], true],
  ["GET", ["creative", "pricing"], true],
  ["POST", ["creative", "prompt"], true],
  ["POST", ["creative", "images"], true],
  // Negative probes: unknown paths and wrong methods must stay unmapped.
  ["GET", ["creative", "prompt"], false],
  ["POST", ["creative", "pricing"], false],
  ["GET", ["videos", "../escape"], false],
  ["GET", ["videos", "vid_not-an-id"], false],
  ["POST", ["models"], false],
  ["GET", ["unknown"], false],
];

async function loadRouteTable() {
  const source = readFileSync(libPath, "utf8");
  const transpiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const tempDir = mkdtempSync(join(tmpdir(), "video-api-routes-"));
  const tempFile = join(tempDir, "video-api-routes.mjs");
  writeFileSync(tempFile, transpiled);
  try {
    return await import(pathToFileURL(tempFile).href);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

function listSourceFiles(directory) {
  const files = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...listSourceFiles(path));
    else if (/\.(ts|tsx)$/.test(entry.name)) files.push(path);
  }
  return files;
}

function extractUiPaths() {
  const found = new Map(); // "segments/joined" -> { file, path }
  const literal = /["'`](\/api\/video[^"'`]*)["'`]/g;
  for (const file of listSourceFiles(join(frontendRoot, "src", "app"))
    .concat(listSourceFiles(join(frontendRoot, "src", "components")))) {
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(literal)) {
      const raw = match[1];
      // The proxy receives only the segments after /api/video/.
      const segments = raw.split("/").filter(Boolean).slice(2).map((segment) => (segment.startsWith("${") ? "*" : segment));
      if (DEDICATED_ROUTES.has(segments.join("/"))) continue;
      found.set(segments.join("/"), { file, segments, raw });
    }
  }
  return found;
}

function covers(methods, segments, matchVideoApiRoute) {
  for (const method of methods) {
    const target = matchVideoApiRoute(method, segments);
    if (target) return target;
  }
  return null;
}

function coversWithWildcard(segments, matchVideoApiRoute) {
  const candidates = segments.map((segment) => {
    if (segment !== "*") return [segment];
    return [JOB_ID, ASSET_ID];
  });
  const expanded = candidates.reduce((accumulator, options) => (
    accumulator.flatMap((prefix) => options.map((option) => [...prefix, option]))
  ), [[]]);
  for (const candidate of expanded) {
    const target = covers(["GET", "POST"], candidate, matchVideoApiRoute);
    if (target) return target;
  }
  return null;
}

const failures = [];
const { matchVideoApiRoute, VIDEO_API_ROUTES } = await loadRouteTable();

for (const [method, segments, shouldMap] of METHOD_PROBES) {
  const mapped = matchVideoApiRoute(method, segments);
  if (shouldMap && !mapped) failures.push(`Missing mapping: ${method} /api/video/${segments.join("/")}`);
  if (!shouldMap && mapped) failures.push(`Unexpected mapping: ${method} /api/video/${segments.join("/")} -> ${mapped}`);
}

const uiPaths = extractUiPaths();
if (uiPaths.size === 0) failures.push("No /api/video/... calls found in client source; the extraction regex may be broken.");
for (const [key, { file, segments, raw }] of uiPaths) {
  const target = coversWithWildcard(segments, matchVideoApiRoute);
  const where = file.replace(frontendRoot, "").replaceAll("\\", "/");
  if (target) console.log(`ok      ${raw}  ->  ${target}  (${where})`);
  else failures.push(`UI calls an unmapped route: ${raw} (${where}) [${key}]`);
}

if (!Array.isArray(VIDEO_API_ROUTES) || VIDEO_API_ROUTES.length < 14) {
  failures.push("VIDEO_API_ROUTES did not load with the expected rules.");
}

if (failures.length) {
  console.error(`\ncheck:routes failed with ${failures.length} problem(s):`);
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}
console.log(`\ncheck:routes passed: ${METHOD_PROBES.length} method probes and ${uiPaths.size} UI route(s) covered.`);
