"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Check, CircleAlert, LoaderCircle, Play } from "lucide-react";
import { Button } from "@/components/ui/button";

type Scene = {
  position: number;
  title: string;
  duration_seconds: number;
  status: string;
  job_status?: string | null;
  image_url?: string;
  video_url?: string;
};

type ConceptVideo = {
  id: string;
  title: string;
  target_seconds: number;
  aspect: "landscape" | "portrait";
  status: string;
  error_code?: string | null;
  video_url?: string;
  scenes: Scene[];
};

const activeStatuses = new Set(["generating", "assembling"]);

function sceneLabel(scene: Scene) {
  if (scene.status === "succeeded") return "Clip ready";
  if (scene.status === "failed" || scene.job_status === "failed") return "Needs attention";
  if (scene.job_status === "succeeded") return "Finishing clip";
  if (scene.status === "generating") return "Creating clip";
  if (scene.status === "image_ready") return "Preparing clip";
  return "Waiting";
}

export function ConceptVideoWorkspace({ id }: { id: string }) {
  const [concept, setConcept] = useState<ConceptVideo | null>(null);
  const [error, setError] = useState("");
  const [retrying, setRetrying] = useState(false);
  const lastStatus = useRef<{ id: string; status: string } | null>(null);
  const current = concept?.id === id ? concept : null;
  const status = current?.status;

  useEffect(() => {
    let active = true;
    let requestNumber = 0;
    async function refresh() {
      const request = ++requestNumber;
      try {
        const response = await fetch(`/api/video/concepts/${encodeURIComponent(id)}`, { cache: "no-store" });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not load this video.");
        if (active && request === requestNumber) {
          const updated = data as ConceptVideo;
          const changed = lastStatus.current?.id !== id || lastStatus.current.status !== updated.status;
          lastStatus.current = { id, status: updated.status };
          setConcept(updated);
          setError("");
          if (changed) window.dispatchEvent(new Event("concepts-changed"));
        }
      } catch (cause) {
        if (active && request === requestNumber) setError(cause instanceof Error ? cause.message : "Could not load this video.");
      }
    }
    void refresh();
    const timer = !status || activeStatuses.has(status) ? setInterval(() => void refresh(), 5000) : undefined;
    const onVisible = () => { if (document.visibilityState === "visible") void refresh(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      active = false;
      if (timer) clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [id, status]);

  async function retry() {
    if (!current || retrying) return;
    setRetrying(true);
    setError("");
    try {
      const response = await fetch(`/api/video/concepts/${encodeURIComponent(id)}/retry`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not retry generation.");
      setConcept(data as ConceptVideo);
      window.dispatchEvent(new Event("concepts-changed"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not retry generation.");
    } finally {
      setRetrying(false);
    }
  }

  if (!current) {
    return <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8 sm:px-8" aria-live="polite">
      <p className="text-sm text-muted-foreground">{error || "Loading your video…"}</p>
    </main>;
  }

  const completed = current.scenes.filter((scene) => scene.status === "succeeded").length;
  const total = current.scenes.length;
  const awaitingApproval = status === "draft" || status === "ready";
  const activeScene = current.scenes.find((scene) => scene.status !== "succeeded");
  const percent = status === "succeeded" ? 100 : status === "assembling" ? 95 : total ? Math.round((completed / total) * 90) : 0;
  const stage = status === "succeeded"
    ? "Video ready"
    : awaitingApproval
      ? "Storyboard awaiting approval"
    : status === "failed"
      ? "Generation stopped"
      : status === "assembling"
        ? "Joining your clips"
        : !activeScene
          ? "Preparing your final video"
        : activeScene.job_status === "succeeded"
          ? `Finishing clip ${completed + 1} of ${total}`
        : activeScene?.status === "generating"
          ? `Creating clip ${completed + 1} of ${total}`
          : activeScene?.status === "image_ready"
            ? `Preparing clip ${completed + 1} of ${total}`
            : `Creating image ${completed + 1} of ${total}`;

  return <main className="mx-auto min-h-0 w-full max-w-4xl flex-1 overflow-y-auto px-4 py-7 sm:px-8 sm:py-10">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-primary">Your video</p>
        <h1 className="mt-2 font-heading text-2xl font-semibold tracking-tight sm:text-3xl">{current.title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{current.target_seconds} seconds · {current.aspect === "portrait" ? "Portrait" : "Landscape"}</p>
      </div>
      <Button variant="outline" nativeButton={false} render={<Link href={`/chat?id=${encodeURIComponent(id)}`} />}>View chat</Button>
    </div>

    {status === "succeeded" && current.video_url ? (
      <section className="mt-7 rounded-2xl border bg-background p-3 shadow-sm sm:p-5" aria-label="Finished video">
        <video key={current.video_url} controls playsInline preload="metadata" src={current.video_url} className={`w-full rounded-xl bg-black ${current.aspect === "portrait" ? "mx-auto max-w-sm aspect-[9/16]" : "aspect-video"}`} aria-label={`Generated video: ${current.title}`} />
        <p className="mt-4 flex items-center gap-2 text-sm font-medium text-emerald-700"><Check className="size-4" /> Your video is ready to watch.</p>
      </section>
    ) : status === "succeeded" ? (
      <p role="status" className="mt-7 rounded-2xl border bg-background p-5 text-sm text-muted-foreground">The video is ready, but its playback link is temporarily unavailable. Reopen this page to try again.</p>
    ) : (
      <section className="mt-7 rounded-2xl border bg-background p-5 shadow-sm sm:p-6" aria-label="Generation progress" aria-live="polite">
        <div className="flex items-center gap-3">
          {status === "failed" ? <CircleAlert className="size-5 text-destructive" /> : awaitingApproval ? <Play className="size-5 text-primary" /> : <LoaderCircle className="size-5 animate-spin text-primary" />}
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold">{stage}</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">{awaitingApproval ? "Return to the chat to approve this plan." : status === "failed" ? "Completed clips are saved." : `${completed} of ${total} scenes complete · Updates automatically`}</p>
          </div>
          {!awaitingApproval && <span className="text-sm font-medium tabular-nums text-muted-foreground">{percent}%</span>}
        </div>
        {!awaitingApproval && <div role="progressbar" aria-label="Video generation progress" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} className="mt-5 h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${percent}%` }} />
        </div>}
        {status === "failed" && <div className="mt-4 flex flex-wrap items-center gap-3">
          <p className="text-sm text-destructive">{current.error_code === "insufficient_credits" ? "More credits are needed to continue." : `Generation stopped: ${current.error_code || "unknown error"}.`}</p>
          <Button size="sm" onClick={() => void retry()} disabled={retrying}>{retrying ? "Retrying…" : "Retry generation"}</Button>
          <p className="w-full text-xs text-muted-foreground">Retrying a failed clip may use more credits.</p>
        </div>}
      </section>
    )}

    <section className="mt-8" aria-labelledby="scene-progress-title">
      <div className="flex items-center justify-between gap-3"><h2 id="scene-progress-title" className="font-heading text-lg font-semibold">Scenes</h2><span className="text-sm tabular-nums text-muted-foreground">{completed} / {total} ready</span></div>
      <ol className="mt-4 space-y-3">
        {current.scenes.map((scene) => {
          const ready = scene.status === "succeeded";
          const running = status !== "failed" && status !== "succeeded" && scene.position === activeScene?.position && status !== "assembling";
          return <li key={scene.position} className="flex items-center gap-4 rounded-xl border bg-background p-3 sm:p-4">
            <div className="flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-primary/10 text-primary">
              {scene.image_url ? <Image unoptimized src={scene.image_url} alt="" width={112} height={112} className="size-full object-cover" /> : ready ? <Check className="size-5" /> : running ? <LoaderCircle className="size-5 animate-spin" /> : <Play className="size-4" />}
            </div>
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{scene.position + 1}. {scene.title}</p><p className="mt-1 text-xs text-muted-foreground">{scene.duration_seconds}s · {running && scene.status === "pending" ? "Creating image" : sceneLabel(scene)}</p></div>
            {ready && <Check className="size-4 shrink-0 text-emerald-600" aria-label="Ready" />}
            {running && <span className="size-2 shrink-0 animate-pulse rounded-full bg-primary" aria-label="In progress" />}
          </li>;
        })}
      </ol>
    </section>
    {error && <p role="alert" className="mt-5 text-sm text-destructive">{error}</p>}
  </main>;
}
