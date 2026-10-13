import { accessTokenForCurrentUser, oauthConfig, sameOrigin } from "@/lib/video-oauth";

const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export async function POST(request: Request) {
  if (!sameOrigin(request)) return Response.json({ detail: "Invalid origin" }, { status: 403 });
  const token = await accessTokenForCurrentUser();
  if (!token) return Response.json({ detail: "Connect your video account" }, { status: 401 });
  if (!request.headers.get("content-type")?.startsWith("multipart/form-data")) {
    return Response.json({ detail: "Image form required" }, { status: 415 });
  }
  const contentLength = Number(request.headers.get("content-length"));
  if (Number.isFinite(contentLength) && contentLength > MAX_IMAGE_BYTES + 64 * 1024) {
    return Response.json({ detail: "Image upload too large" }, { status: 413 });
  }
  const form = await request.formData();
  const image = form.get("file");
  if (!(image instanceof File) || !TYPES.has(image.type) || image.size < 1 || image.size > MAX_IMAGE_BYTES) {
    return Response.json({ detail: "Upload a JPEG, PNG, or WebP image up to 10 MB" }, { status: 422 });
  }
  try {
    const created = await fetch(`${oauthConfig().apiBase}/v1/assets`, {
      method: "POST", cache: "no-store", signal: AbortSignal.timeout(30_000),
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ content_type: image.type }),
    });
    const asset = await created.json();
    if (!created.ok) return Response.json(asset, { status: created.status });
    const uploadForm = new FormData();
    for (const [key, value] of Object.entries(asset.upload.fields as Record<string, string>)) uploadForm.set(key, value);
    uploadForm.set("file", image, image.name);
    const uploaded = await fetch(asset.upload.url, {
      method: "POST", body: uploadForm, cache: "no-store", signal: AbortSignal.timeout(120_000),
    });
    if (!uploaded.ok) return Response.json({ detail: "Image upload failed" }, { status: 502 });
    return Response.json({ asset_id: asset.asset_id });
  } catch {
    return Response.json({ detail: "Image upload unavailable" }, { status: 502 });
  }
}
