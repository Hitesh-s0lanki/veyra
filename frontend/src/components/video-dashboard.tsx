"use client";

import { UserButton, useUser } from "@clerk/nextjs";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, ImagePlus, Plus, WalletCards, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupLabel, SidebarHeader, SidebarInset, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { Textarea } from "@/components/ui/textarea";

type Profile = { model_id: string; modes: string[]; duration_seconds: number[]; resolutions: string[]; parameter_defaults: Record<string, number> };
type Wallet = { balance_cents: number };
type Job = { job_id: string; model_id: string; status: string; mode?: string; prompt?: string; duration_seconds?: number; resolution?: string; created_at?: string; price_cents?: number; error_code?: string };
type VideoInput = { model_id: string; mode: "t2v" | "i2v"; prompt: string; duration_seconds: number; resolution: string; parameters: Record<string, number>; input_asset_id?: string; seed?: number };
type Aspect = "landscape" | "portrait" | "square";
type PromptTemplate = { slug: string; title: string; style: string; prompt: string };

// Motion prompts and posters from reports/marketing_videos.json and public/videos.
const promptTemplates: PromptTemplate[] = [
  { slug: "clay-astronaut", title: "Clay Astronaut", style: "Clay animation", prompt: "The clay astronaut takes two slow buoyant steps forward, then raises one arm and waves cheerfully as its helmet glints. The camera dollies in gently, keeping the flag and ringed planet behind it." },
  { slug: "paper-city", title: "Paper City", style: "Paper craft", prompt: "The little paper tram glides steadily from left to right along its track while warm windows light up one by one across the square. The camera slowly pushes in toward the central fountain." },
  { slug: "watercolor-koi", title: "Watercolor Koi", style: "Watercolor", prompt: "The two koi swim along their circular path, their tails stirring fresh pigment blooms that swirl outward across the paper while lily leaves drift at the edge. The camera glides slowly clockwise above the pond." },
  { slug: "pixel-train", title: "Pixel Train", style: "Pixel art", prompt: "The pixel train rolls steadily across the bridge from left to right, its glowing windows reflecting on the luminous river below as stars blink overhead. The camera tracks smoothly alongside the train." },
  { slug: "ink-fox", title: "Ink Fox", style: "Ink painting", prompt: "The ink fox bounds forward two strides through the brushstroke forest, then pauses and lifts its nose as the glowing firefly rises slowly past it. The camera tracks gently to follow the fox." },
  { slug: "origami-dragon", title: "Origami Dragon", style: "Paper art", prompt: "A creased origami dragon unfolds its wings from a folded mountain peak, then breathes a ribbon of glittering golden paper flames across the sky. The camera cranes slowly upward over the papercraft valley." },
];

// Mirrors the verified profiles in src/config.py so the composer remains visible while the API is down.
const fallbackModels: Profile[] = [
  { model_id: "ltx-2.3-distilled", modes: ["t2v", "i2v"], duration_seconds: [5, 10, 20], resolutions: ["512p", "512p-portrait", "720p", "720p-portrait"], parameter_defaults: {} },
  { model_id: "wan-2.2", modes: ["t2v"], duration_seconds: [5], resolutions: ["720p", "720p-portrait"], parameter_defaults: { inference_steps: 10, guidance_scale: 5 } },
  { model_id: "hunyuanvideo-1.5", modes: ["t2v"], duration_seconds: [5], resolutions: ["480p", "480p-portrait"], parameter_defaults: { inference_steps: 10, guidance_scale: 6 } },
  { model_id: "cogvideox-1.5", modes: ["t2v"], duration_seconds: [5], resolutions: ["480p", "480p-portrait"], parameter_defaults: { inference_steps: 10, guidance_scale: 6 } },
];
const names: Record<string, string> = { "ltx-2.3-distilled": "LTX 2.3", "wan-2.2": "Wan 2.2", "hunyuanvideo-1.5": "HunyuanVideo 1.5", "cogvideox-1.5": "CogVideoX 1.5" };
const money = (cents: number) => `$${(cents / 100).toFixed(2)}`;
const title = (job: Job) => job.prompt?.trim().slice(0, 55) || names[job.model_id] || "Untitled video";
const statusStyles: Record<string, string> = {
  queued: "bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  running: "bg-blue-50 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  succeeded: "bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  failed: "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200",
  cancelled: "bg-muted text-muted-foreground",
};
const statusLabel = (status: string) => status.charAt(0).toUpperCase() + status.slice(1);

function VideoStatus({ status }: { status: string }) {
  return <span className={`inline-flex w-fit rounded-md px-2 py-0.5 text-xs font-medium ${statusStyles[status] ?? "bg-muted text-muted-foreground"}`}>{statusLabel(status)}</span>;
}
const aspectLabel: Record<Aspect, string> = { landscape: "Landscape", portrait: "Portrait", square: "Square" };
const aspectRatio: Record<Aspect, number> = { landscape: 16 / 9, portrait: 9 / 16, square: 1 };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...init });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${response.status}).`);
  return data as T;
}

async function cropImage(file: File, aspect: Aspect): Promise<File> {
  const image = await createImageBitmap(file);
  try {
    if (image.width < 256 || image.height < 256 || image.width * image.height > 16_000_000) {
      throw new Error("Image must be at least 256 × 256 pixels and no more than 16 million pixels.");
    }
    const ratio = aspectRatio[aspect];
    const width = Math.min(image.width, Math.round(image.height * ratio));
    const height = Math.min(image.height, Math.round(image.width / ratio));
    if (width < 256 || height < 256) throw new Error(`This image is too small for ${aspectLabel[aspect].toLowerCase()} cropping. Choose a larger image.`);
    const canvas = document.createElement("canvas");
    canvas.width = width; canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Could not prepare the image.");
    context.fillStyle = "#fff";
    context.fillRect(0, 0, width, height);
    context.drawImage(image, (image.width - width) / 2, (image.height - height) / 2, width, height, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    if (!blob) throw new Error("Could not prepare the image.");
    if (blob.size > 10 * 1024 * 1024) throw new Error("Prepared image exceeds the 10 MB upload limit.");
    return new File([blob], "video-source.jpg", { type: "image/jpeg" });
  } finally { image.close(); }
}

function HistoryButton({ job, selected, onSelect }: { job: Job; selected: boolean; onSelect: () => void }) {
  const { setOpenMobile } = useSidebar();
  return <SidebarMenuItem><SidebarMenuButton type="button" onClick={() => { onSelect(); setOpenMobile(false); }} isActive={selected} className="h-auto min-h-11 flex-col items-stretch gap-2 px-3 py-3">
    <div className="truncate text-sm font-medium">{title(job)}</div>
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1"><VideoStatus status={job.status} />{job.created_at && <span className="text-xs text-muted-foreground">{new Date(job.created_at).toLocaleDateString(undefined, { dateStyle: "medium" })}</span>}</div>
  </SidebarMenuButton></SidebarMenuItem>;
}

function NewVideoButton({ onClick }: { onClick: () => void }) {
  const { setOpenMobile } = useSidebar();
  return <Button type="button" className="w-full justify-start" onClick={() => { onClick(); setOpenMobile(false); }}><Plus aria-hidden="true" /> New video</Button>;
}

export function VideoDashboard() {
  const { isLoaded, isSignedIn } = useUser();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [models, setModels] = useState<Profile[]>(fallbackModels);
  const [modelId, setModelId] = useState(fallbackModels[0].model_id);
  const [duration, setDuration] = useState(5);
  const [resolution, setResolution] = useState("512p");
  const [parameters, setParameters] = useState<Record<string, number>>({});
  const [seed, setSeed] = useState("");
  const [prompt, setPrompt] = useState("");
  const [aspect, setAspect] = useState<Aspect>("landscape");
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [assetId, setAssetId] = useState("");
  const [uploadedAspect, setUploadedAspect] = useState<Aspect | null>(null);
  const sourceInput = useRef<HTMLInputElement>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [preview, setPreview] = useState<{ jobId: string; url: string } | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [apiReady, setApiReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState("");
  const pendingSubmission = useRef<{ input: VideoInput; key: string } | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [creditsNotice, setCreditsNotice] = useState(false);
  const [completionToasts, setCompletionToasts] = useState<Array<{ jobId: string; name: string }>>([]);
  const observedStatuses = useRef<Map<string, string> | null>(null);
  const notifiedCompletions = useRef(new Set<string>());
  const completionToast = completionToasts[0];

  const profile = useMemo(() => models.find((item) => item.model_id === modelId) ?? models[0], [models, modelId]);
  const selectedJobId = searchParams.get("video");
  const selectedJob = jobs.find((job) => job.job_id === selectedJobId);
  const mode: "t2v" | "i2v" = sourceFile ? "i2v" : "t2v";
  const invalidate = () => { pendingSubmission.current = null; };
  function showVideo(id: string | null) {
    const params = new URLSearchParams(searchParams.toString());
    if (id) params.set("video", id); else params.delete("video");
    const query = params.toString();
    router.push(`${pathname}${query ? `?${query}` : ""}`, { scroll: false });
  }

  const refresh = useCallback(async () => {
    const [jobsResult, walletResult] = await Promise.allSettled([
      request<{ videos: Job[] }>("/api/video/videos"), request<Wallet>("/api/video/wallet"),
    ]);
    if (jobsResult.status === "fulfilled") {
      const latestJobs = jobsResult.value.videos;
      const previous = observedStatuses.current;
      if (previous) {
        const completed = latestJobs.filter((job) =>
          job.status === "succeeded" &&
          ["queued", "running"].includes(previous.get(job.job_id) ?? "") &&
          !notifiedCompletions.current.has(job.job_id));
        if (completed.length) {
          completed.forEach((job) => notifiedCompletions.current.add(job.job_id));
          setCompletionToasts((current) => [...current, ...completed.map((job) => ({ jobId: job.job_id, name: title(job) }))]);
        }
      }
      observedStatuses.current = new Map(latestJobs.map((job) => [job.job_id, job.status]));
      setJobs(latestJobs);
    }
    if (walletResult.status === "fulfilled") setWallet(walletResult.value);
  }, [setCompletionToasts]);

  const loadWorkspace = useCallback(async () => {
    try {
      const data = await request<{ models: Profile[] }>("/api/video/models");
      if (!data.models.length) throw new Error("No video models are available.");
      setModels(data.models);
      setApiReady(true); setApiError("");
      setModelId((current) => data.models.some((item) => item.model_id === current) ? current : data.models[0].model_id);
      await refresh();
    } catch (error) {
      setApiReady(false);
      setApiError(error instanceof Error ? error.message : "Video API unavailable");
    } finally { setLoading(false); }
  }, [refresh]);

  useEffect(() => {
    if (!isSignedIn) return;
    let active = true;
    queueMicrotask(() => { if (active) void loadWorkspace(); });
    return () => { active = false; };
  }, [isSignedIn, loadWorkspace]);
  useEffect(() => {
    if (!apiReady || !jobs.some((job) => ["queued", "running"].includes(job.status))) return;
    const timer = setInterval(() => { void refresh(); }, 5000);
    return () => clearInterval(timer);
  }, [apiReady, jobs, refresh]);
  useEffect(() => {
    if (!completionToast) return;
    const timer = setTimeout(() => setCompletionToasts((current) => current.slice(1)), 8000);
    return () => clearTimeout(timer);
  }, [completionToast]);
  useEffect(() => {
    if (!selectedJobId || selectedJob?.status !== "succeeded") return;
    let active = true;
    request<{ video_url: string }>(`/api/video/videos/${selectedJobId}/download`)
      .then((result) => { if (active) setPreview({ jobId: selectedJobId, url: result.video_url }); })
      .catch(() => { if (active) setPreview(null); });
    return () => { active = false; };
  }, [selectedJobId, selectedJob?.status]);
  useEffect(() => () => { if (sourceUrl) URL.revokeObjectURL(sourceUrl); }, [sourceUrl]);

  function removeSource() {
    setSourceFile(null); setSourceUrl(""); setAssetId(""); setUploadedAspect(null); setAspect("landscape");
    if (sourceInput.current) sourceInput.current.value = "";
    invalidate();
  }

  async function chooseSource(file: File | null) {
    if (!file) { removeSource(); return; }
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 10 * 1024 * 1024) {
      setMessage("Choose a JPEG, PNG, or WebP image under 10 MB."); return;
    }
    try {
      const image = await createImageBitmap(file);
      const ratio = image.width / image.height;
      image.close();
      setAspect(ratio >= 1.2 ? "landscape" : ratio <= 1 / 1.2 ? "portrait" : "square");
      setSourceFile(file); setSourceUrl(URL.createObjectURL(file)); setAssetId(""); setUploadedAspect(null); setMessage(""); invalidate();
      const imageModel = models.find((item) => item.modes.includes("i2v"));
      if (imageModel && !profile?.modes.includes("i2v")) {
        setModelId(imageModel.model_id); setDuration(imageModel.duration_seconds[0]); setResolution(imageModel.resolutions[0]); setParameters(imageModel.parameter_defaults);
      }
    } catch { setMessage("Choose a valid image file."); }
  }

  function chooseModel(id: string) {
    const selected = models.find((item) => item.model_id === id);
    if (!selected) return;
    if (sourceFile && !selected.modes.includes("i2v")) removeSource();
    setModelId(id); setDuration(selected.duration_seconds[0]); setResolution(selected.resolutions[0]); setParameters(selected.parameter_defaults); invalidate();
  }

  async function uploadSource(): Promise<string> {
    if (!sourceFile) throw new Error("Attach an image first.");
    if (assetId && uploadedAspect === aspect) return assetId;
    const cropped = await cropImage(sourceFile, aspect);
    const form = new FormData(); form.set("file", cropped);
    const uploaded = await request<{ asset_id: string }>("/api/video/assets/upload", { method: "POST", body: form });
    setAssetId(uploaded.asset_id); setUploadedAspect(aspect);
    return uploaded.asset_id;
  }

  function videoInput(chosenAsset: string): VideoInput {
    if (!profile || !prompt.trim()) throw new Error("Describe your video first.");
    const numberSeed = seed.trim() ? Number(seed) : undefined;
    if (numberSeed !== undefined && (!Number.isInteger(numberSeed) || numberSeed < 0 || numberSeed > 4294967295)) throw new Error("Seed must be an integer from 0 to 4294967295.");
    return { model_id: modelId, mode, prompt: prompt.trim(), duration_seconds: duration,
      resolution: mode === "t2v" && aspect === "portrait" ? `${resolution}-portrait` : resolution, parameters,
      ...(mode === "i2v" ? { input_asset_id: chosenAsset } : {}), ...(numberSeed === undefined ? {} : { seed: numberSeed }) };
  }

  async function submitVideo() {
    if (!apiReady) { setMessage("Connect the video API before generating."); return; }
    setBusy("video"); setMessage("");
    try {
      const submission = pendingSubmission.current ?? {
        input: videoInput(sourceFile ? await uploadSource() : ""),
        key: crypto.randomUUID(),
      };
      pendingSubmission.current = submission;
      const job = await request<Job>("/api/video/videos", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": submission.key }, body: JSON.stringify(submission.input) });
      observedStatuses.current?.set(job.job_id, job.status);
      setJobs((current) => [job, ...current.filter((item) => item.job_id !== job.job_id)]);
      showVideo(job.job_id); invalidate();
      await refresh();
    } catch (error) { setMessage(`${error instanceof Error ? error.message : "Could not submit video."} You can retry Generate safely.`); }
    finally { setBusy(""); }
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
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not update this video."); }
    finally { setBusy(""); }
  }

  function newVideo() {
    showVideo(null); setPrompt(""); setSeed(""); setMessage(""); removeSource();
    const first = models[0];
    if (first) { setModelId(first.model_id); setDuration(first.duration_seconds[0]); setResolution(first.resolutions[0]); setParameters(first.parameter_defaults); }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function applyTemplate(template: PromptTemplate) {
    const templateModel = models.find((item) => item.model_id === "ltx-2.3-distilled" && item.modes.includes("i2v"));
    if (!templateModel) { setMessage("The image-to-video model for this template is unavailable."); return; }
    setBusy("template"); setMessage("");
    try {
      const response = await fetch(`/videos/${template.slug}.jpg`);
      if (!response.ok) throw new Error("Could not load the template image.");
      const file = new File([await response.blob()], `${template.slug}.jpg`, { type: "image/jpeg" });
      await chooseSource(file);
      setModelId(templateModel.model_id);
      setDuration(templateModel.duration_seconds.includes(5) ? 5 : templateModel.duration_seconds[0]);
      setResolution(templateModel.resolutions.includes("720p") ? "720p" : templateModel.resolutions[0]);
      setParameters(templateModel.parameter_defaults);
      setSeed(""); setPrompt(template.prompt); invalidate();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not load the template."); }
    finally { setBusy(""); }
  }

  return <SidebarProvider>
    <Sidebar collapsible="offcanvas" className="border-r border-sidebar-border">
      <SidebarHeader className="gap-4 border-b border-sidebar-border p-4">
        <Link href="/" className="flex items-center gap-2.5 rounded-md text-lg font-semibold tracking-tight focus-visible:outline-2 focus-visible:outline-offset-2"><Image src="/veyra-mark.png" alt="" width={446} height={445} priority className="size-8 shrink-0 object-contain" /> <span>Veyra Studio</span></Link>
        <NewVideoButton onClick={newVideo} />
      </SidebarHeader>
      <SidebarContent><SidebarGroup className="min-h-0 flex-1"><SidebarGroupLabel>Videos</SidebarGroupLabel><ScrollArea className="min-h-0 flex-1"><SidebarMenu className="px-1 pb-4">
        {jobs.map((job) => <HistoryButton key={job.job_id} job={job} selected={selectedJobId === job.job_id} onSelect={() => showVideo(job.job_id)} />)}
        {!jobs.length && <p className="px-2 py-4 text-sm text-muted-foreground">Your generated videos will appear here.</p>}
      </SidebarMenu></ScrollArea></SidebarGroup></SidebarContent>
      <SidebarFooter className="gap-0 border-t border-sidebar-border p-0">
        <div className="px-4 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-medium text-muted-foreground">Credits remaining</p>
              <p className={wallet ? "mt-1 text-xl font-semibold tracking-tight tabular-nums" : "mt-1 text-sm text-muted-foreground"} aria-live="polite">{wallet ? money(wallet.balance_cents) : loading ? "Checking balance…" : "Balance unavailable"}</p>
            </div>
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><WalletCards className="size-4" strokeWidth={1.8} aria-hidden="true" /></span>
          </div>
          <Button type="button" variant="outline" size="sm" className="mt-3 w-full justify-between border-sidebar-border bg-sidebar px-3 text-sidebar-foreground" onClick={() => setCreditsNotice(true)}>Add credits <Plus className="size-3.5 text-primary" aria-hidden="true" /></Button>
          {creditsNotice && <p role="status" className="mt-2 text-xs leading-4 text-muted-foreground">Credit top-ups are not available yet.</p>}
        </div>
        <div className="flex items-center justify-between gap-3 border-t border-sidebar-border px-4 py-3"><span className="text-sm text-muted-foreground">Your account</span><UserButton /></div>
      </SidebarFooter>
    </Sidebar>
    <SidebarInset className="min-w-0 bg-[#fafaf9]">
      <div className="flex h-14 items-center gap-3 border-b bg-background px-4 sm:px-8"><SidebarTrigger aria-label="Toggle video history" /><span className="truncate text-sm font-medium text-muted-foreground">{selectedJob ? title(selectedJob) : "New video"}</span></div>
      <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-4 py-8 sm:px-8 sm:py-14">
        {selectedJob ? <section className="space-y-6" aria-labelledby="selected-video-title">
          <div><p className="text-sm text-muted-foreground">Your video</p><h1 id="selected-video-title" className="mt-2 font-heading text-3xl font-semibold tracking-tight">{title(selectedJob)}</h1><div className="mt-3 flex flex-wrap items-center gap-3"><VideoStatus status={selectedJob.status} />{selectedJob.created_at && <span className="text-sm text-muted-foreground">{new Date(selectedJob.created_at).toLocaleString()}</span>}</div></div>
          <Card><CardHeader><CardTitle>Generation details</CardTitle><CardDescription>{names[selectedJob.model_id] ?? selectedJob.model_id} · {selectedJob.mode === "i2v" ? "Image to video" : "Text to video"}</CardDescription></CardHeader><CardContent className="space-y-5">
            {preview?.jobId === selectedJob.job_id && <video key={preview.url} controls playsInline preload="metadata" src={preview.url} className="aspect-video w-full rounded-lg bg-black" aria-label={`Generated video: ${title(selectedJob)}`} />}
            {selectedJob.prompt && <p className="whitespace-pre-wrap text-sm">{selectedJob.prompt}</p>}
            <div className="flex flex-wrap gap-2 text-sm text-muted-foreground"><span className="rounded-md bg-muted px-3 py-1">{selectedJob.duration_seconds ?? "—"} seconds</span><span className="rounded-md bg-muted px-3 py-1">{selectedJob.resolution ?? "—"}</span>{typeof selectedJob.price_cents === "number" && <span className="rounded-md bg-muted px-3 py-1">{money(selectedJob.price_cents)}</span>}</div>
            {selectedJob.error_code && <p role="alert" className="text-sm text-destructive">Generation failed: {selectedJob.error_code}</p>}
            {selectedJob.status === "succeeded" && <Button type="button" disabled={!!busy} onClick={() => void jobAction(selectedJob.job_id, "download")}>Open video</Button>}
            {["queued", "running"].includes(selectedJob.status) && <Button type="button" variant="outline" disabled={!!busy} onClick={() => void jobAction(selectedJob.job_id, "cancel")}>Cancel generation</Button>}
          </CardContent></Card>
          {message && <p role="alert" className="rounded-lg border bg-muted px-4 py-3 text-sm">{message}</p>}
        </section> : selectedJobId ? <section className="space-y-4" aria-labelledby="missing-video-title">
          <h1 id="missing-video-title" className="font-heading text-2xl font-semibold">{loading ? "Loading video…" : apiError ? "Could not load this video" : "Video not found"}</h1>
          {apiError && <p role="alert" className="text-sm text-muted-foreground">{apiError}</p>}
          {!loading && <div className="flex gap-2"><Button type="button" variant="outline" onClick={() => showVideo(null)}>New video</Button>{apiError && <Button type="button" onClick={() => { setLoading(true); void loadWorkspace(); }}>Retry</Button>}</div>}
        </section> : <section className="flex flex-1 flex-col justify-center gap-6" aria-labelledby="composer-title">
          <div className="text-center"><h1 id="composer-title" className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">What will you create?</h1><p className="mt-2 text-sm text-muted-foreground">Describe a scene. Add an image to bring it to life.</p></div>
          {!!apiError && <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"><span>{apiError}. Your draft is still available, but generation needs the video API.</span><Button type="button" size="sm" variant="outline" disabled={loading} onClick={() => { setLoading(true); void loadWorkspace(); }}>Retry connection</Button></div>}
          <Card className="gap-0 rounded-2xl py-0 shadow-sm"><CardContent className="space-y-5 p-4 sm:p-6">
            <Textarea aria-label="Video prompt" className="min-h-36 resize-y border-0 px-0 text-base shadow-none focus-visible:border-0 focus-visible:ring-0 sm:text-base" maxLength={2000} placeholder="A cinematic shot of a quiet street at sunrise. The camera moves slowly forward…" value={prompt} onChange={(event) => { setPrompt(event.target.value); invalidate(); }} />
            {sourceFile && <div className="flex items-start gap-3 rounded-xl bg-muted p-3"><div className="h-20 shrink-0 overflow-hidden rounded-lg bg-background" style={{ width: 80 * aspectRatio[aspect], aspectRatio: aspectRatio[aspect] }}><Image unoptimized src={sourceUrl} width={320} height={320} alt="Source image crop preview" className="h-full w-full object-cover" /></div><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{sourceFile.name}</p><p className="mt-1 text-xs text-muted-foreground">Center cropped to {aspectLabel[aspect].toLowerCase()} before upload</p></div><Button type="button" size="icon-sm" variant="ghost" aria-label="Remove image" onClick={removeSource}><X aria-hidden="true" /></Button></div>}
            <div className="flex flex-wrap items-end gap-3 border-t pt-4">
              <div><Input ref={sourceInput} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" aria-label="Attach a source image" onChange={(event) => void chooseSource(event.target.files?.[0] ?? null)} /><Button type="button" variant="outline" className="h-9" onClick={() => sourceInput.current?.click()}><ImagePlus aria-hidden="true" /> {sourceFile ? "Change image" : "Add image"}</Button></div>
              <span className="ml-auto text-xs text-muted-foreground">{prompt.length} / 2000</span>
            </div>
            <div className="grid gap-3 border-t pt-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="grid min-w-0 gap-1.5">
                <label htmlFor="video-model" className="text-xs font-medium text-muted-foreground">Model</label>
                <Select value={modelId} onValueChange={(value) => { if (value) chooseModel(value); }}>
                  <SelectTrigger id="video-model" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>{models.map((item) => <SelectItem key={item.model_id} value={item.model_id}>{names[item.model_id] ?? item.model_id}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="grid min-w-0 gap-1.5">
                <label htmlFor="video-length" className="text-xs font-medium text-muted-foreground">Length</label>
                <Select value={String(duration)} onValueChange={(value) => { if (value) { setDuration(Number(value)); invalidate(); } }}>
                  <SelectTrigger id="video-length" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>{profile?.duration_seconds.map((item) => <SelectItem key={item} value={String(item)}>{item} seconds</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="grid min-w-0 gap-1.5">
                <label htmlFor="video-quality" className="text-xs font-medium text-muted-foreground">Quality</label>
                <Select value={resolution} onValueChange={(value) => { if (value) { setResolution(value); invalidate(); } }}>
                  <SelectTrigger id="video-quality" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>{profile?.resolutions.filter((item) => !item.endsWith("-portrait")).map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="grid min-w-0 gap-1.5">
                <label htmlFor="video-aspect-ratio" className="text-xs font-medium text-muted-foreground">Aspect ratio</label>
                <Select value={aspect} onValueChange={(value) => { if (value === "landscape" || value === "portrait" || (sourceFile && value === "square")) { setAspect(value); setAssetId(""); setUploadedAspect(null); invalidate(); } }}>
                  <SelectTrigger id="video-aspect-ratio" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="landscape">Landscape</SelectItem>{(sourceFile || profile?.resolutions.includes(`${resolution}-portrait`)) && <SelectItem value="portrait">Portrait</SelectItem>}{sourceFile && <SelectItem value="square">Square</SelectItem>}</SelectContent>
                </Select>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">{sourceFile ? "Image to video · the source is center cropped; the model follows its framing. Output dimensions are approximate." : "Text to video · choose landscape or portrait output."}</p>
            <details className="text-sm"><summary className="cursor-pointer text-muted-foreground">More settings</summary><div className="mt-3 grid gap-3 sm:grid-cols-2">{Object.keys(profile?.parameter_defaults ?? {}).map((key) => <label key={key} className="grid gap-1.5 text-xs font-medium">{key === "inference_steps" ? "Inference steps" : "Guidance scale"}<Input type="number" min={key === "inference_steps" ? 1 : 0} max={key === "inference_steps" ? 100 : 20} step={key === "inference_steps" ? 1 : 0.1} value={parameters[key] ?? ""} onChange={(event) => { setParameters((current) => ({ ...current, [key]: Number(event.target.value) })); invalidate(); }} /></label>)}<label className="grid gap-1.5 text-xs font-medium">Seed (optional)<Input type="number" min={0} max={4294967295} step={1} value={seed} onChange={(event) => { setSeed(event.target.value); invalidate(); }} /></label></div></details>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4"><span className="text-sm text-muted-foreground">{wallet ? `${money(wallet.balance_cents)} available credit` : loading ? "Connecting to video API…" : "Cost deducted from your balance when you generate"}</span><Button type="button" size="lg" disabled={!isLoaded || !isSignedIn || !apiReady || !prompt.trim() || !!busy} onClick={() => void submitVideo()}>{busy === "video" ? "Starting…" : "Generate"}</Button></div>
          </CardContent></Card>
          {message && <p role="alert" className="rounded-lg border bg-muted px-4 py-3 text-sm">{message}</p>}
          <section className="space-y-4 pt-4" aria-labelledby="templates-title">
            <div><h2 id="templates-title" className="font-heading text-2xl font-semibold tracking-tight">Prompt templates</h2><p className="mt-1 text-sm text-muted-foreground">Pick a look. We&apos;ll add its image, prompt, and settings to the editor.</p></div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {promptTemplates.map((template, index) => <button key={template.slug} type="button" disabled={!!busy || !models.some((item) => item.model_id === "ltx-2.3-distilled" && item.modes.includes("i2v"))} onClick={() => void applyTemplate(template)} aria-label={`Use ${template.title} image and prompt template`} className="group overflow-hidden rounded-[1.25rem] bg-white text-left shadow-sm ring-1 ring-black/5 transition duration-200 hover:-translate-y-1 hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0">
                <span className="relative block aspect-[3/2] overflow-hidden bg-muted">
                  <Image src={`/videos/${template.slug}.jpg`} alt="" fill sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 300px" className="object-cover transition duration-500 group-hover:scale-105" />
                  <span className="absolute inset-0 bg-gradient-to-t from-black/75 via-transparent to-black/20" aria-hidden="true" />
                  <span className="absolute left-3 top-3 rounded-full border border-white/60 bg-black/20 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur-sm">{String(index + 1).padStart(2, "0")}</span>
                  <span className="absolute bottom-3 left-4 right-4 text-white"><span className="block text-[11px] font-medium uppercase tracking-[0.16em] text-white/80">{template.style}</span><span className="mt-1 block font-heading text-xl font-semibold leading-tight">{template.title}</span></span>
                </span>
                <span className="flex min-h-12 items-center justify-between gap-2 px-4 text-xs font-medium text-muted-foreground"><span>Image → video <span aria-hidden="true">·</span> LTX 2.3 <span aria-hidden="true">·</span> 5s <span aria-hidden="true">·</span> 720p</span><ArrowUpRight className="size-4 shrink-0 text-primary transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" aria-hidden="true" /></span>
              </button>)}
            </div>
          </section>
          <section className="rounded-xl border bg-background p-5" aria-labelledby="settings-guide-title">
            <h2 id="settings-guide-title" className="font-heading text-lg font-semibold">What you can set</h2>
            <dl className="mt-3 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
              <div><dt className="font-medium">Prompt and image</dt><dd className="text-muted-foreground">Describe the action and camera movement. Add an image to guide the first frame.</dd></div>
              <div><dt className="font-medium">Model</dt><dd className="text-muted-foreground">Choose the generator. Available lengths, quality, and image support change with the model.</dd></div>
              <div><dt className="font-medium">Length and quality</dt><dd className="text-muted-foreground">Select clip duration and output resolution from the model&apos;s supported options.</dd></div>
              <div><dt className="font-medium">Aspect ratio</dt><dd className="text-muted-foreground">Choose landscape or portrait for text to video. With an image, choose landscape, portrait, or square cropping.</dd></div>
              <div><dt className="font-medium">More settings</dt><dd className="text-muted-foreground">Set a seed to repeat a variation. Some models also offer inference steps and guidance scale.</dd></div>
            </dl>
          </section>
        </section>}
      </div>
    </SidebarInset>
    {completionToast && <div role="status" aria-live="polite" className="fixed bottom-4 right-4 z-50 w-[calc(100vw-2rem)] max-w-sm rounded-xl border border-emerald-200 bg-background p-4 shadow-lg sm:bottom-6 sm:right-6">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0"><p className="font-semibold text-emerald-800 dark:text-emerald-300">Video ready</p><p className="mt-1 truncate text-sm text-muted-foreground">{completionToast.name}</p></div>
        <Button type="button" variant="ghost" size="icon-sm" aria-label="Dismiss notification" onClick={() => setCompletionToasts((current) => current.slice(1))}><X aria-hidden="true" /></Button>
      </div>
      <Button type="button" size="sm" className="mt-3" onClick={() => { showVideo(completionToast.jobId); setCompletionToasts((current) => current.slice(1)); }}>View video</Button>
    </div>}
  </SidebarProvider>;
}
