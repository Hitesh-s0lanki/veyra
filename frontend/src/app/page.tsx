"use client";

import { useUser } from "@clerk/nextjs";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { VideoShowcase } from "@/components/video-showcase";
import { HeroReel } from "@/components/hero-reel";
import { HowItWorks } from "@/components/marketing-sections";
import { MotionConfig } from "motion/react";

type Profile = { model_id: string; modes: string[]; duration_seconds: number[]; resolutions: string[]; parameter_defaults: Record<string, number> };
type Wallet = { balance_cents: number; balance_usd: string; initial_credit_cents: number };
type Pricing = { prompt_cents: number; image_cents: number };
type Quote = { amount_cents: number; amount_usd: string; model_id: string; mode: string; duration_seconds: number; resolution: string };
type Asset = { asset_id: string; content_type: string; created_at: string };
type Job = { job_id: string; model_id: string; status: string; mode?: string; prompt?: string; duration_seconds?: number; resolution?: string; created_at?: string; price_cents?: number; error_code?: string };
type VideoInput = { model_id: string; mode: string; prompt: string; duration_seconds: number; resolution: string; parameters: Record<string, number>; input_asset_id?: string; seed?: number };
type Draft = { prompt: string; summary: string; model_id: string; mode: string; duration_seconds: number; resolution: string; parameters: Record<string, number> };
type Txn = { id: number; kind: string; amount_cents: number; balance_after_cents: number; created_at: string };

const field = "min-h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";
const label = "grid gap-1.5 text-sm font-medium";
const names: Record<string, string> = { "ltx-2.3-distilled": "LTX 2.3 Distilled", "wan-2.2": "Wan 2.2", "hunyuanvideo-1.5": "HunyuanVideo 1.5", "cogvideox-1.5": "CogVideoX 1.5" };
const money = (cents: number) => `$${(cents / 100).toFixed(2)}`;
const signedMoney = (cents: number) => `${cents < 0 ? "-" : "+"}$${(Math.abs(cents) / 100).toFixed(2)}`;
const kindNames: Record<string, string> = { starter_grant: "Signup credit", reserve: "Reserved", refund: "Refund" };
const headers = () => ({ "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() });

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...init });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${response.status}).`);
  return data as T;
}

export default function Home() {
  const { isLoaded, isSignedIn } = useUser();
  const [connected, setConnected] = useState(false);
  const [models, setModels] = useState<Profile[]>([]);
  const [modelId, setModelId] = useState("");
  const [mode, setMode] = useState("t2v");
  const [duration, setDuration] = useState(5);
  const [resolution, setResolution] = useState("");
  const [parameters, setParameters] = useState<Record<string, number>>({});
  const [seed, setSeed] = useState("");
  const [prompt, setPrompt] = useState("");
  const [imagePrompt, setImagePrompt] = useState("");
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const sourceInput = useRef<HTMLInputElement>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceOrientation, setSourceOrientation] = useState<"landscape" | "portrait" | "square" | null>(null);
  const [assetId, setAssetId] = useState("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [txns, setTxns] = useState<Txn[]>([]);
  const [pricing, setPricing] = useState<Pricing | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [quotedInput, setQuotedInput] = useState<VideoInput | null>(null);
  const [quoteKey, setQuoteKey] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [imageResult, setImageResult] = useState<{ asset_id: string; image_url: string } | null>(null);
  const [confirmAction, setConfirmAction] = useState<"creative" | "image" | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");

  const profile = useMemo(() => models.find((item) => item.model_id === modelId), [models, modelId]);
  const invalidate = () => { setQuote(null); setQuotedInput(null); setQuoteKey(""); };
  const refresh = useCallback(async () => {
    const [newWallet, newJobs, newAssets, newTxns] = await Promise.all([
      request<Wallet>("/api/video/wallet"),
      request<{ videos: Job[] }>("/api/video/videos"),
      request<{ assets: Asset[] }>("/api/video/assets"),
      request<{ transactions: Txn[] }>("/api/video/wallet/transactions"),
    ]);
    setWallet(newWallet); setJobs(newJobs.videos); setAssets(newAssets.assets);
    setTxns(newTxns.transactions.filter((txn) => txn.amount_cents !== 0));
  }, []);

  useEffect(() => {
    if (!isSignedIn) return;
    let active = true;
    (async () => {
      try {
        const status = await request<{ connected: boolean }>("/api/oauth/status");
        if (!active) return;
        setConnected(status.connected);
        if (!status.connected) return;
        const [data, prices] = await Promise.all([
          request<{ models: Profile[] }>("/api/video/models"),
          request<Pricing>("/api/video/creative/pricing"),
        ]);
        if (!active) return;
        setModels(data.models); setPricing(prices);
        const first = data.models[0];
        if (first) { setModelId(first.model_id); setMode(first.modes[0]); setDuration(first.duration_seconds[0]); setResolution(first.resolutions[0]); setParameters(first.parameter_defaults); }
        await refresh();
      } catch (error) { if (active) setMessage(error instanceof Error ? error.message : "Could not load workspace."); }
    })();
    return () => { active = false; };
  }, [isSignedIn, refresh]);

  useEffect(() => {
    if (!connected || !jobs.some((job) => ["queued", "running"].includes(job.status))) return;
    const timer = setInterval(() => { void refresh().catch(() => setMessage("Could not refresh job status.")); }, 5000);
    return () => clearInterval(timer);
  }, [connected, jobs, refresh]);

  function chooseSource(file: File | null) {
    if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    setSourceFile(file);
    setSourceUrl(file ? URL.createObjectURL(file) : "");
    setSourceOrientation(null);
    setAssetId("");
    setImageResult(null);
    invalidate();
    if (!file && sourceInput.current) sourceInput.current.value = "";
    if (file) {
      const imageModel = profile?.modes.includes("i2v") ? profile : models.find((item) => item.modes.includes("i2v"));
      if (imageModel && imageModel.model_id !== modelId) chooseModel(imageModel.model_id);
      setMode("i2v");
    } else {
      setMode("t2v");
    }
  }

  function chooseModel(id: string) {
    const selected = models.find((item) => item.model_id === id);
    if (!selected) return;
    setModelId(id); setMode(selected.modes[0]); setDuration(selected.duration_seconds[0]);
    setResolution(selected.resolutions[0]); setParameters(selected.parameter_defaults); invalidate(); setDraft(null);
    if (!selected.modes.includes("i2v")) {
      if (sourceUrl) URL.revokeObjectURL(sourceUrl);
      setSourceFile(null); setSourceUrl(""); setSourceOrientation(null); setAssetId("");
      if (sourceInput.current) sourceInput.current.value = "";
      if (sourceFile || assetId) setMessage("This model supports text-to-video only, so the source image was removed.");
    }
  }

  async function uploadSource(): Promise<string> {
    if (!sourceFile) return assetId;
    if (sourceFile.size > 10 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(sourceFile.type)) throw new Error("Choose a JPEG, PNG, or WebP image under 10 MB.");
    let image: ImageBitmap;
    try { image = await createImageBitmap(sourceFile); }
    catch { throw new Error("Choose a valid JPEG, PNG, or WebP image."); }
    const { width, height } = image;
    image.close();
    if (width < 256 || height < 256 || width * height > 16_000_000) throw new Error("Image must be at least 256 × 256 pixels and no more than 16 million pixels.");
    const form = new FormData(); form.set("file", sourceFile);
    const uploaded = await request<{ asset_id: string }>("/api/video/assets/upload", { method: "POST", body: form });
    setAssetId(uploaded.asset_id); setSourceFile(null);
    void refresh().catch(() => {});
    return uploaded.asset_id;
  }

  function videoInput(chosenAsset: string): VideoInput {
    if (!profile || !prompt.trim()) throw new Error("Write a video prompt first.");
    if (mode === "i2v" && !chosenAsset) throw new Error("Choose or upload a source image.");
    const numberSeed = seed.trim() ? Number(seed) : undefined;
    if (numberSeed !== undefined && (!Number.isInteger(numberSeed) || numberSeed < 0 || numberSeed > 4294967295)) throw new Error("Seed must be an integer from 0 to 4294967295.");
    return { model_id: modelId, mode, prompt: prompt.trim(), duration_seconds: duration, resolution, parameters,
      ...(mode === "i2v" ? { input_asset_id: chosenAsset } : {}), ...(numberSeed === undefined ? {} : { seed: numberSeed }) };
  }

  async function reviewVideo() {
    setBusy("quote"); setMessage(""); invalidate();
    try {
      const input = videoInput(mode === "i2v" ? await uploadSource() : "");
      const result = await request<Quote>("/api/video/videos/quote", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) });
      setQuotedInput(input); setQuote(result); setQuoteKey(crypto.randomUUID());
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not quote video."); }
    finally { setBusy(""); }
  }

  async function submitVideo() {
    if (!quote || !quotedInput || !quoteKey) return;
    if (wallet && wallet.balance_cents < quote.amount_cents) { setMessage("Insufficient credit for this video."); return; }
    setBusy("video"); setMessage("");
    try {
      const job = await request<Job>("/api/video/videos", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": quoteKey }, body: JSON.stringify(quotedInput) });
      setJobs((current) => [job, ...current.filter((item) => item.job_id !== job.job_id)]);
      invalidate();
      setMessage(`Video ${job.status}. Its status will update automatically.`);
      void refresh().catch(() => setMessage(`Video ${job.status}. Your library could not refresh yet; reload to check it.`));
    } catch (error) { setMessage(`${error instanceof Error ? error.message : "Could not submit video."} Retry with the same quote to avoid a duplicate charge.`); }
    finally { setBusy(""); }
  }

  async function creativeAction(action: "creative" | "image") {
    if (!pricing) return;
    const cost = action === "creative" ? pricing.prompt_cents : pricing.image_cents;
    if (wallet && cost > wallet.balance_cents) { setMessage("Insufficient credit for this action."); return; }
    setBusy(action); setMessage(""); setConfirmAction(null);
    try {
      if (action === "creative") {
        if (!prompt.trim()) throw new Error("Write an idea in the video prompt first.");
        const chosen = mode === "i2v" ? await uploadSource() : "";
        if (mode === "i2v" && !chosen) throw new Error("Choose a source image first.");
        const result = await request<Draft>("/api/video/creative/prompt", { method: "POST", headers: headers(),
          body: JSON.stringify({ model_id: modelId, mode, idea: prompt.trim(), duration_seconds: duration, ...(chosen ? { input_asset_id: chosen } : {}) }) });
        setDraft(result); setMessage("Creative draft ready. Review it before applying.");
      } else {
        if (!imagePrompt.trim()) throw new Error("Describe the image first.");
        const chosen = sourceFile ? await uploadSource() : assetId;
        const result = await request<{ asset_id: string; image_url: string }>("/api/video/creative/images", { method: "POST", headers: headers(),
          body: JSON.stringify({ prompt: imagePrompt.trim(), ...(chosen ? { source_asset_id: chosen } : {}) }) });
        setImageResult(result); setAssetId(result.asset_id); invalidate();
        const imageModel = models.find((item) => item.modes.includes("i2v"));
        if (imageModel && imageModel.model_id !== modelId) chooseModel(imageModel.model_id);
        setMode("i2v"); await refresh();
        setMessage("Image saved to your assets and selected for image-to-video.");
      }
    } catch (error) { setMessage(error instanceof Error ? error.message : "Creative request failed."); }
    finally { setBusy(""); }
  }

  async function openAsset(id: string) {
    try {
      const result = await request<{ url: string }>(`/api/video/assets/${id}/download`);
      window.open(result.url, "_blank", "noopener,noreferrer");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not open image."); }
  }

  async function jobAction(id: string, action: "cancel" | "download") {
    setBusy(id); setMessage("");
    try {
      if (action === "cancel") await request(`/api/video/videos/${id}/cancel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      else {
        const result = await request<{ video_url: string }>(`/api/video/videos/${id}/download`);
        window.open(result.video_url, "_blank", "noopener,noreferrer");
      }
      await refresh();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Job action failed."); }
    finally { setBusy(""); }
  }

  async function disconnect() {
    try { await request("/api/oauth/disconnect", { method: "POST" }); setConnected(false); setModels([]); setWallet(null); setJobs([]); setAssets([]); setTxns([]); invalidate(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not disconnect."); }
  }

  return <MotionConfig reducedMotion="user">
    <main className="mx-auto flex w-full max-w-[1500px] flex-1 flex-col gap-14 px-4 py-6 sm:gap-20 sm:px-6 sm:py-10 lg:px-10">
    <HeroReel />
    <VideoShowcase />

    <section id="create" className="scroll-mt-8 space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-600">Workspace</p><h2 className="mt-1 text-3xl font-semibold tracking-tight">Create a video</h2></div>
        {wallet && <div className="rounded-xl border bg-card px-5 py-3 text-right"><p className="text-xs text-muted-foreground">Available credit</p><p className="text-2xl font-semibold tabular-nums">{money(wallet.balance_cents)}</p></div>}</div>
      {!isLoaded ? <p>Loading account…</p> : !isSignedIn ? <Card><CardContent className="flex flex-col items-start justify-between gap-5 py-7 sm:flex-row sm:items-center"><div><h3 className="text-lg font-semibold">Your studio starts here</h3><p className="mt-1 text-sm text-muted-foreground">Sign in to create your first video with $2 in credit.</p></div><Link href="/sign-in" className="inline-flex min-h-11 items-center justify-center rounded-full bg-primary px-6 text-sm font-semibold text-primary-foreground transition hover:bg-primary/85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">Sign in to create</Link></CardContent></Card> : !connected ?
        <Card><CardHeader><CardTitle>Connect your video account</CardTitle><CardDescription>Authorize this app with your Clerk account.</CardDescription></CardHeader><CardContent><a href="/api/oauth/start" className="inline-flex rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground">Connect account</a></CardContent></Card> :
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]">
          <Card><CardHeader><CardTitle>Video settings</CardTitle><CardDescription>Only settings enabled by the API appear here.</CardDescription></CardHeader><CardContent className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className={label}>Model<select className={field} value={modelId} onChange={(e) => chooseModel(e.target.value)}>{models.map((item) => <option key={item.model_id} value={item.model_id}>{names[item.model_id] ?? item.model_id}</option>)}</select></label>
              <label className={label}>Mode<select className={field} value={mode} onChange={(e) => { if (e.target.value === "t2v") chooseSource(null); else { setMode("i2v"); invalidate(); } }}>{profile?.modes.map((item) => <option key={item} value={item}>{item === "i2v" ? "Image to video" : "Text to video"}</option>)}</select></label>
              <label className={label}>Duration<select className={field} value={duration} onChange={(e) => { setDuration(Number(e.target.value)); invalidate(); }}>{profile?.duration_seconds.map((item) => <option key={item} value={item}>{item} seconds</option>)}</select></label>
              <label className={label}>Resolution<select className={field} value={resolution} onChange={(e) => { setResolution(e.target.value); invalidate(); }}>{profile?.resolutions.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
            </div>
            <label className={label}>Prompt<textarea className={`${field} min-h-36 resize-y`} maxLength={2000} placeholder="Describe the subject, motion, camera, lighting, and style…" value={prompt} onChange={(e) => { setPrompt(e.target.value); invalidate(); setDraft(null); }} /><span className="text-right text-xs font-normal text-muted-foreground">{prompt.length} / 2000</span></label>
            <div className="space-y-3 rounded-xl border p-4"><p className="text-sm font-medium">Source image <span className="font-normal text-muted-foreground">(optional)</span></p><input ref={sourceInput} type="file" accept="image/jpeg,image/png,image/webp" className="block w-full text-sm" onChange={(e) => chooseSource(e.target.files?.[0] ?? null)} /><p className="text-xs text-muted-foreground">JPEG, PNG, or WebP · max 10 MB · minimum 256 × 256 pixels. Adding one switches to image-to-video and uploads it to private S3 before the quote.</p>{sourceUrl && <img src={sourceUrl} alt="Selected source" onLoad={(e) => { const ratio = e.currentTarget.naturalWidth / e.currentTarget.naturalHeight; setSourceOrientation(ratio >= 1.2 ? "landscape" : ratio <= 1 / 1.2 ? "portrait" : "square"); }} className="max-h-64 w-full rounded-lg bg-muted object-contain" />}
              {!!assets.length && <label className={label}>Or reuse an uploaded image<select className={field} value={assetId} onChange={(e) => { const id = e.target.value; if (sourceUrl) URL.revokeObjectURL(sourceUrl); setSourceFile(null); setSourceUrl(""); setSourceOrientation(null); if (sourceInput.current) sourceInput.current.value = ""; setAssetId(id); if (id) { const imageModel = profile?.modes.includes("i2v") ? profile : models.find((item) => item.modes.includes("i2v")); if (imageModel && imageModel.model_id !== modelId) chooseModel(imageModel.model_id); setMode("i2v"); } else setMode("t2v"); invalidate(); }}><option value="">Choose an image</option>{assets.map((asset) => <option key={asset.asset_id} value={asset.asset_id}>{asset.asset_id} · {new Date(asset.created_at).toLocaleDateString()}</option>)}</select></label>}
              {(sourceUrl || assetId) && <Button type="button" size="sm" variant="outline" onClick={() => chooseSource(null)}>Remove source image</Button>}
              <p className="text-xs text-muted-foreground">Output framing: {mode === "t2v" ? "landscape (current text-to-video workers)" : sourceOrientation ? `${sourceOrientation} from your image` : "follows the uploaded image (landscape, portrait, or square)"}. The current API does not offer a separate orientation setting.</p>
            </div>
            <details className="rounded-xl border p-4"><summary className="cursor-pointer text-sm font-medium">Advanced settings</summary><div className="mt-4 grid gap-4 sm:grid-cols-2">
              {Object.keys(profile?.parameter_defaults ?? {}).map((key) => <label className={label} key={key}>{key === "inference_steps" ? "Inference steps" : "Guidance scale"}<input className={field} type="number" min={key === "inference_steps" ? 1 : 0} max={key === "inference_steps" ? 100 : 20} step={key === "inference_steps" ? 1 : 0.1} value={parameters[key] ?? ""} onChange={(e) => { setParameters((current) => ({ ...current, [key]: Number(e.target.value) })); invalidate(); }} /></label>)}
              <label className={label}>Seed (optional)<input className={field} type="number" min={0} max={4294967295} step={1} value={seed} onChange={(e) => { setSeed(e.target.value); invalidate(); }} /></label>
            </div></details>
            <Button type="button" size="lg" disabled={!profile || !!busy} onClick={reviewVideo}>{busy === "quote" ? "Preparing quote…" : "Review video price"}</Button>
          </CardContent></Card>
          <div className="space-y-6"><Card><CardHeader><CardTitle>Price and confirmation</CardTitle><CardDescription>Review the exact price before starting a video.</CardDescription></CardHeader><CardContent className="space-y-4">
            {quote ? <><div className="rounded-xl bg-muted p-4"><p className="text-sm text-muted-foreground">{names[quote.model_id] ?? quote.model_id} · {quote.duration_seconds}s · {quote.resolution}</p><p className="mt-2 text-3xl font-semibold">{money(quote.amount_cents)}</p></div><Button type="button" size="lg" disabled={!!busy || (!!wallet && quote.amount_cents > wallet.balance_cents)} onClick={submitVideo}>{busy === "video" ? "Submitting…" : "Confirm and generate"}</Button>{wallet && quote.amount_cents > wallet.balance_cents && <p className="text-sm text-destructive">Insufficient credit.</p>}</> : <p className="text-sm text-muted-foreground">Select “Review video price” to see the charge.</p>}
          </CardContent></Card><Card><CardHeader><CardTitle>Credit history</CardTitle><CardDescription>Recent activity from your credit ledger. The $2.00 signup credit is granted once.</CardDescription></CardHeader><CardContent className="space-y-3">
            {txns.length ? txns.slice(0, 10).map((txn) => <div key={txn.id} className="flex items-start justify-between gap-2 text-sm">
              <div><p>{kindNames[txn.kind] ?? txn.kind}</p><p className="text-xs text-muted-foreground">{new Date(txn.created_at).toLocaleString()}</p></div>
              <div className="text-right"><p className={`tabular-nums ${txn.amount_cents > 0 ? "text-emerald-600" : ""}`}>{signedMoney(txn.amount_cents)}</p><p className="text-xs text-muted-foreground tabular-nums">Balance {money(txn.balance_after_cents)}</p></div>
            </div>) : <p className="text-sm text-muted-foreground">No credit activity yet.</p>}
          </CardContent></Card><Card><CardHeader><CardTitle>Account</CardTitle></CardHeader><CardContent><button type="button" className="text-sm underline" onClick={disconnect}>Disconnect video account</button></CardContent></Card></div>
        </div>}
      {message && <p role="alert" className="rounded-lg border bg-muted px-4 py-3 text-sm">{message}</p>}
    </section>

    {connected && <section className="grid gap-6 lg:grid-cols-2">
      <Card><CardHeader><CardTitle>Creative agent</CardTitle><CardDescription>Turn your current idea into a model-aware, editable video prompt. {pricing && `Cost: ${money(pricing.prompt_cents)}.`}</CardDescription></CardHeader><CardContent className="space-y-4">
        {confirmAction === "creative" ? <div className="rounded-xl border p-4"><p className="text-sm">Charge {money(pricing?.prompt_cents ?? 0)} from your credit to optimize this prompt?</p><div className="mt-3 flex gap-2"><Button type="button" disabled={!!busy || !pricing || (!!wallet && wallet.balance_cents < pricing.prompt_cents)} onClick={() => void creativeAction("creative")}>Confirm optimization</Button><Button type="button" variant="outline" onClick={() => setConfirmAction(null)}>Back</Button></div></div> : <Button type="button" variant="outline" disabled={!!busy || !prompt.trim()} onClick={() => setConfirmAction("creative")}>Review creative agent price</Button>}
        {draft && <div className="space-y-3 rounded-xl bg-muted p-4"><p className="text-xs font-medium uppercase text-muted-foreground">Agent suggestion</p><p className="text-sm">{draft.summary}</p><p className="whitespace-pre-wrap text-sm">{draft.prompt}</p><Button type="button" onClick={() => { setPrompt(draft.prompt); setModelId(draft.model_id); setMode(draft.mode); setDuration(draft.duration_seconds); setResolution(draft.resolution); setParameters(draft.parameters); setDraft(null); invalidate(); }}>Apply editable draft</Button></div>}
      </CardContent></Card>
      <Card><CardHeader><CardTitle>Create or edit an image</CardTitle><CardDescription>Generate an image or select an existing image above to edit. {pricing && `Cost: ${money(pricing.image_cents)}.`}</CardDescription></CardHeader><CardContent className="space-y-4">
        <label className={label}>Image instructions<textarea className={`${field} min-h-24 resize-y`} maxLength={2000} value={imagePrompt} onChange={(e) => { setImagePrompt(e.target.value); setConfirmAction(null); }} placeholder="A cinematic frame of a quiet city at sunrise…" /></label>
        {confirmAction === "image" ? <div className="rounded-xl border p-4"><p className="text-sm">Charge {money(pricing?.image_cents ?? 0)} from your credit to {assetId || sourceFile ? "edit" : "generate"} this image?</p><div className="mt-3 flex gap-2"><Button type="button" disabled={!!busy || !pricing || (!!wallet && wallet.balance_cents < pricing.image_cents)} onClick={() => void creativeAction("image")}>Confirm image</Button><Button type="button" variant="outline" onClick={() => setConfirmAction(null)}>Back</Button></div></div> : <Button type="button" variant="outline" disabled={!!busy || !imagePrompt.trim()} onClick={() => setConfirmAction("image")}>Review image price</Button>}
        {imageResult && <div className="space-y-2"><img src={imageResult.image_url} alt="Generated image" className="max-h-72 w-full rounded-lg bg-muted object-contain" /><p className="text-xs text-muted-foreground">Image saved to your assets. Its preview link expires in one hour.</p></div>}
      </CardContent></Card>
    </section>}

    {connected && <section className="space-y-4"><h2 className="text-3xl font-semibold tracking-tight">Your videos</h2>{jobs.length ? <div className="grid gap-4 sm:grid-cols-2">{jobs.map((job) => <Card key={job.job_id}><CardHeader><CardTitle>{names[job.model_id] ?? job.model_id}</CardTitle><CardDescription>{job.created_at ? new Date(job.created_at).toLocaleString() : job.job_id}</CardDescription></CardHeader><CardContent className="space-y-3"><div className="flex flex-wrap gap-2 text-xs"><span className="rounded-full bg-muted px-2.5 py-1 capitalize">{job.status}</span>{job.duration_seconds && <span>{job.duration_seconds}s · {job.resolution}</span>}{typeof job.price_cents === "number" && <span>{money(job.price_cents)}</span>}</div>{job.prompt && <p className="line-clamp-3 text-sm">{job.prompt}</p>}{job.error_code && <p className="text-sm text-destructive">{job.error_code}</p>}<div>{job.status === "succeeded" && <Button type="button" size="sm" disabled={!!busy} onClick={() => void jobAction(job.job_id, "download")}>Open video</Button>}{["queued", "running"].includes(job.status) && <Button type="button" size="sm" variant="outline" disabled={!!busy} onClick={() => void jobAction(job.job_id, "cancel")}>Cancel job</Button>}</div></CardContent></Card>)}</div> : <Card><CardContent><p className="text-sm text-muted-foreground">Your generated videos will appear here.</p></CardContent></Card>}</section>}
    {connected && !!assets.length && <section className="space-y-4"><h2 className="text-3xl font-semibold tracking-tight">Your images</h2><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{assets.map((asset) => <Card key={asset.asset_id}><CardContent className="space-y-2"><p className="truncate text-sm font-medium">{asset.asset_id}</p><p className="text-xs text-muted-foreground">{asset.content_type} · {new Date(asset.created_at).toLocaleString()}</p><div className="flex gap-2"><Button type="button" size="sm" variant="outline" onClick={() => void openAsset(asset.asset_id)}>Preview</Button><Button type="button" size="sm" variant="outline" onClick={() => { const ltx = models.find((item) => item.modes.includes("i2v")); if (ltx) chooseModel(ltx.model_id); setMode("i2v"); setAssetId(asset.asset_id); setSourceFile(null); invalidate(); document.getElementById("create")?.scrollIntoView({ behavior: "smooth" }); }}>Use in video</Button></div></CardContent></Card>)}</div></section>}
    <HowItWorks />
  </main>
  </MotionConfig>;
}
