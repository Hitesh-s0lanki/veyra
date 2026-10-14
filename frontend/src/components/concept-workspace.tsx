"use client";

import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Dialog } from "@base-ui/react/dialog";
import {
  ArrowUp,
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleHelp,
  Film,
  Sparkles,
  Sprout,
  TrainFront,
  Wind,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

type Scene = {
  title: string;
  duration_seconds: number;
  image_prompt: string;
  motion_prompt: string;
};
type Plan = { title: string; summary: string; scenes: Scene[] };
type Question = {
  prompt: string;
  options: { label: string; description?: string }[];
};
type Message = {
  role: "user" | "assistant";
  content: string;
  question?: Question;
};
type GeneratedScene = Scene & {
  position: number;
  status: string;
  job_status?: string;
  job_error?: string;
  image_url?: string;
  video_url?: string;
};
type Concept = {
  id: string;
  title: string;
  target_seconds: number;
  aspect: "landscape" | "portrait";
  status: string;
  messages: Message[];
  plan: Plan | null;
  revision: number;
  estimated_cost_cents?: number;
  error_code?: string | null;
  video_url?: string;
  scenes: GeneratedScene[];
};
type IdeaTemplate = {
  title: string;
  style: string;
  preview: string;
  prompt: string;
  seconds: number;
  aspect: "landscape" | "portrait";
};

const ideaTemplates: IdeaTemplate[] = [
  {
    title: "Paper City Wakes",
    style: "Paper craft · gentle adventure",
    preview:
      "A tram conductor lights up a sleeping paper town and finds its first passenger at sunrise.",
    prompt:
      "Create a family-friendly story set in a miniature city made from folded paper and painted cardstock. At dawn, a small paper tram conductor finds the town dark and empty. As the tram moves through the streets, its warm windows light the bakery, market, and apartment blocks one by one. Show the conductor noticing a child waiting alone at the final stop, then slowing down to welcome them aboard. End with the tram crossing a bridge as the whole city glows in the sunrise. Keep the conductor and tram visually consistent across scenes. Use layered paper textures, soft amber light, gentle tracking shots, and the quiet sounds of wheels, paper rustling, and morning birds. No narration or on-screen text.",
    seconds: 60,
    aspect: "landscape",
  },
  {
    title: "The Lost Kite",
    style: "Watercolor · seaside story",
    preview:
      "A child follows a runaway red kite through a windy harbor town, then launches it again with a new friend.",
    prompt:
      "Tell a warm, family-friendly story about a child whose red kite slips away on a windy afternoon in a small harbor town. Begin with the kite lifting out of the child's hands beside the pier. Follow the child through narrow streets as a fishmonger points toward the hill and a cyclist helps spot the kite above the rooftops. At the lighthouse, the child finds it caught safely on a low railing. End with the child and cyclist launching it together over the sea as the clouds open. Keep the red kite and the child's blue raincoat consistent across scenes. Use soft watercolor edges, lively wind in clothing and flags, clear camera movement that follows the search, and natural harbor sounds. No dialogue or on-screen text.",
    seconds: 45,
    aspect: "landscape",
  },
  {
    title: "Robot's First Garden",
    style: "Clay animation · hopeful",
    preview:
      "A small robot plants a found seed in an abandoned greenhouse and opens the shutters for its first sprout.",
    prompt:
      "Make a hopeful, family-friendly story about a palm-sized maintenance robot in an abandoned greenhouse. The robot discovers a seed beneath a broken pot, clears a patch of soil, and carefully plants it. A leaking pipe gives it just enough water; the robot repairs the pipe and waits through the night. At sunrise, a fresh sprout appears and the robot opens the dusty shutters to let the light in. End with a wider view of the greenhouse beginning to bloom around it. Keep the robot's scratched metal body and single blue eye consistent across scenes. Use tactile clay animation, damp soil, glass reflections, close views of its small hand movements, a slow camera pullback for the ending, and gentle mechanical and rain sounds. No narration or on-screen text.",
    seconds: 60,
    aspect: "landscape",
  },
];

async function api<T>(
  path: string,
  method = "GET",
  payload?: unknown,
): Promise<T> {
  const response = await fetch(`/api/video/concepts${path}`, {
    method,
    cache: "no-store",
    headers:
      payload === undefined
        ? undefined
        : { "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status})`,
    );
  return data as T;
}

const errorText = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";

export function ConceptWorkspace() {
  const router = useRouter();
  const search = useSearchParams();
  const selectedId = search.get("id") ?? search.get("concept");
  const [concept, setConcept] = useState<Concept | null>(null);
  const [draft, setDraft] = useState<Plan | null>(null);
  const [idea, setIdea] = useState("");
  const [pendingMessage, setPendingMessage] = useState("");
  const [selectedAnswer, setSelectedAnswer] = useState("");
  const [target, setTarget] = useState(60);
  const [aspect, setAspect] = useState<"landscape" | "portrait">("landscape");
  const [busy, setBusy] = useState("");
  const [confirmGeneration, setConfirmGeneration] = useState(false);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const ideaInput = useRef<HTMLTextAreaElement>(null);
  const conversationScroll = useRef<HTMLDivElement>(null);
  const storyboardRef = useRef<HTMLElement>(null);
  const latestReply = useRef<HTMLDivElement>(null);
  const lastReplyCount = useRef(0);

  const notifyConceptsChanged = () =>
    window.dispatchEvent(new Event("concepts-changed"));

  const loadConcept = useCallback(async (id: string) => {
    const result = await api<Concept>(`/${id}`);
    setConcept(result);
    setDraft(result.plan);
  }, []);
  const conceptStatus = concept?.status;

  useEffect(() => {
    let active = true;
    (selectedId ? api<Concept>(`/${selectedId}`) : Promise.resolve(null))
      .then((current) => {
        if (active) {
          setConcept(current);
          setDraft(current?.plan ?? null);
          setError("");
        }
      })
      .catch((cause) => {
        if (active) setError(errorText(cause));
      })
      .finally(() => {
        if (active) setLoaded(true);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (
      !selectedId ||
      !conceptStatus ||
      !["generating", "assembling"].includes(conceptStatus)
    )
      return;
    const timer = setInterval(() => {
      void loadConcept(selectedId)
        .then(notifyConceptsChanged)
        .catch((cause) => setError(errorText(cause)));
    }, 5000);
    return () => clearInterval(timer);
  }, [selectedId, conceptStatus, loadConcept]);

  const total = useMemo(
    () =>
      draft?.scenes.reduce((sum, scene) => sum + scene.duration_seconds, 0) ??
      0,
    [draft],
  );
  const changed =
    JSON.stringify(draft ?? null) !== JSON.stringify(concept?.plan ?? null);

  useEffect(() => {
    if (pendingMessage && conversationScroll.current)
      conversationScroll.current.scrollTop = conversationScroll.current.scrollHeight;
  }, [pendingMessage]);

  useEffect(() => {
    const count = concept?.messages.length ?? 0;
    if (
      count > lastReplyCount.current &&
      concept?.messages[count - 1]?.role === "assistant"
    ) {
      setAnnouncement(concept.messages[count - 1].content);
      latestReply.current?.focus();
      if (concept.plan) storyboardRef.current?.scrollIntoView({ block: "nearest" });
    }
    lastReplyCount.current = count;
  }, [concept?.messages, concept?.plan]);

  useEffect(() => {
    if (!changed) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [changed]);

  const select = useCallback(
    (id: string | null) => {
      if (id === selectedId) return true;
      if (changed && !window.confirm("Discard your unsaved storyboard edits?"))
        return false;
      setError("");
      setIdea("");
      setConcept(null);
      setDraft(null);
      setSelectedAnswer("");
      router.push(
        id ? `/chat?id=${encodeURIComponent(id)}` : "/app?mode=concept",
        {
          scroll: false,
        },
      );
      return true;
    },
    [changed, router, selectedId],
  );

  useEffect(() => {
    const handleSelect = (event: Event) => {
      if (!select((event as CustomEvent<string | null>).detail))
        event.preventDefault();
    };
    window.addEventListener("concept-select", handleSelect);
    return () => window.removeEventListener("concept-select", handleSelect);
  }, [select]);

  async function send(answer?: string) {
    const message = (answer ?? idea).trim();
    if (!message || busy) return;
    if (
      changed &&
      !window.confirm(
        "Your unsaved storyboard edits will be replaced by the assistant's new plan. Continue?",
      )
    )
      return;
    setBusy("chat");
    setError("");
    setPendingMessage(message);
    setIdea("");
    setSelectedAnswer("");
    let createdId: string | null = null;
    try {
      let current = concept;
      if (!current) {
        current = await api<Concept>("", "POST", {
          target_seconds: target,
          aspect,
        });
        createdId = current.id;
      }
      const updated = await api<Concept>(`/${current.id}/chat`, "POST", {
        message,
        revision: current.revision,
      });
      setConcept(updated);
      setDraft(updated.plan);
      if (!selectedId)
        router.replace(`/chat?id=${encodeURIComponent(current.id)}`, {
          scroll: false,
        });
      notifyConceptsChanged();
    } catch (cause) {
      setError(errorText(cause));
      setIdea(message);
      if (createdId)
        router.replace(`/chat?id=${encodeURIComponent(createdId)}`, {
          scroll: false,
        });
      if (createdId) notifyConceptsChanged();
      else if (selectedId && !concept)
        await loadConcept(selectedId).catch(() => {});
    } finally {
      setPendingMessage("");
      setBusy("");
    }
  }

  async function savePlan() {
    if (!concept || !draft || busy) return;
    setBusy("save");
    setError("");
    try {
      const updated = await api<Concept>(`/${concept.id}/plan`, "PUT", {
        revision: concept.revision,
        plan: draft,
      });
      setConcept(updated);
      setDraft(updated.plan);
      notifyConceptsChanged();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  async function generate() {
    if (!concept || busy || changed) return;
    setBusy("generate");
    setError("");
    try {
      const updated = await api<Concept>(`/${concept.id}/generate`, "POST", {});
      setConcept(updated);
      notifyConceptsChanged();
      router.push(`/app?concept=${encodeURIComponent(updated.id)}`, { scroll: false });
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  async function retry() {
    if (!concept || busy) return;
    setBusy("retry");
    setError("");
    try {
      const updated = await api<Concept>(`/${concept.id}/retry`, "POST", {});
      setConcept(updated);
      notifyConceptsChanged();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  function updateScene(index: number, patch: Partial<Scene>) {
    setDraft((current) =>
      current
        ? {
            ...current,
            scenes: current.scenes.map((scene, position) =>
              position === index ? { ...scene, ...patch } : scene,
            ),
          }
        : current,
    );
  }

  function applyIdeaTemplate(template: IdeaTemplate) {
    setIdea(template.prompt);
    setTarget(template.seconds);
    setAspect(template.aspect);
    setError("");
    ideaInput.current?.focus();
  }

  const editing = !!concept && ["draft", "ready"].includes(concept.status);

  const hasStoryboard = !!draft || !!concept?.scenes.length;
  const hasConversation = !!concept?.messages.length || !!pendingMessage;
  const visibleMessages: Message[] = [
    ...(concept?.messages ?? []),
    ...(pendingMessage ? [{ role: "user" as const, content: pendingMessage }] : []),
  ];
  const lastMessage = concept?.messages.at(-1);

  if (selectedId && !concept && busy !== "chat")
    return (
      <main
        className="flex flex-1 flex-col items-center justify-center gap-3 text-sm text-muted-foreground"
        role={error ? "alert" : "status"}
      >
        {error || "Loading concept…"}
        {error && (
          <Button type="button" variant="outline" onClick={() => select(null)}>
            Start a new concept
          </Button>
        )}
      </main>
    );

  if (!hasConversation && !hasStoryboard)
    return (
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-4 py-8 sm:px-8 sm:py-14">
        <section
          className="flex flex-1 flex-col justify-center gap-6"
          aria-labelledby="concept-composer-title"
        >
          <div className="text-center">
            <h1
              id="concept-composer-title"
              className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl"
            >
              What will you create?
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Describe your idea. We&apos;ll shape it into a video up to 60
              seconds.
            </p>
          </div>
          <Card className="gap-0 rounded-2xl py-0 shadow-sm">
            <CardContent className="space-y-5 p-4 sm:p-6">
              <Textarea
                ref={ideaInput}
                aria-label="Describe your video idea"
                value={idea}
                onChange={(event) => setIdea(event.target.value)}
                maxLength={4000}
                rows={5}
                className="min-h-36 resize-y border-0 px-0 text-base shadow-none focus-visible:border-0 focus-visible:ring-0 sm:text-base"
                placeholder="A short story about a paper city coming to life at sunrise…"
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void send();
                  }
                }}
              />
              <div className="flex flex-wrap items-end justify-between gap-4 border-t pt-4">
                <div className="flex flex-wrap gap-3">
                  <div className="grid gap-1.5">
                    <label
                      htmlFor="concept-length"
                      className="text-xs font-medium text-muted-foreground"
                    >
                      Length
                    </label>
                    <Select
                      value={String(target)}
                      onValueChange={(value) => {
                        if (value) setTarget(Number(value));
                      }}
                    >
                      <SelectTrigger
                        id="concept-length"
                        className="h-9 min-w-36 bg-background"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[5, 10, 15, 20, 30, 45, 60].map((length) => (
                          <SelectItem key={length} value={String(length)}>
                            {length} seconds
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-1.5">
                    <label
                      htmlFor="concept-format"
                      className="text-xs font-medium text-muted-foreground"
                    >
                      Format
                    </label>
                    <Select
                      value={aspect}
                      onValueChange={(value) => {
                        if (value === "landscape" || value === "portrait")
                          setAspect(value);
                      }}
                    >
                      <SelectTrigger
                        id="concept-format"
                        className="h-9 min-w-36 bg-background"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="landscape">Landscape</SelectItem>
                        <SelectItem value="portrait">Portrait</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button
                  type="button"
                  disabled={!idea.trim() || !!busy}
                  onClick={() => void send()}
                >
                  Start chatting <ArrowUp className="size-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </section>
        <section
          className="space-y-4 pt-10"
          aria-labelledby="concept-templates-title"
        >
          <div className="w-full flex flex-col items-center justify-center ">
            <h2
              id="concept-templates-title"
              className="font-heading text-2xl font-semibold tracking-tight"
            >
              Idea templates
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Choose a story to fill the editor, then change any details before
              chatting.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {ideaTemplates.map((template, index) => {
              const ArtworkIcon =
                index === 0 ? TrainFront : index === 1 ? Wind : Sprout;
              const artwork = [
                "from-[#f7cfab] via-[#f2a7a5] to-[#8c95da]",
                "from-[#a9dce7] via-[#a9c9e8] to-[#efadc3]",
                "from-[#b9d9a8] via-[#88c6ab] to-[#80a9be]",
              ][index];
              return (
                <button
                  key={template.title}
                  type="button"
                  aria-label={`Use ${template.title} idea template`}
                  aria-pressed={idea === template.prompt}
                  onClick={() => applyIdeaTemplate(template)}
                  className="group flex h-full flex-col overflow-hidden rounded-[1.25rem] border bg-background text-left shadow-sm transition-[transform,box-shadow,border-color] duration-150 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary active:scale-[0.96] motion-reduce:transform-none aria-pressed:border-primary aria-pressed:ring-2 aria-pressed:ring-primary/20"
                >
                  <span
                    className={`relative block h-32 w-full overflow-hidden bg-gradient-to-br ${artwork}`}
                    aria-hidden="true"
                  >
                    <span className="absolute -right-10 -top-20 size-52 rounded-full border-[24px] border-white/20" />
                    <span className="absolute -bottom-20 left-8 size-44 rounded-full bg-white/15" />
                    <span className="absolute bottom-4 left-5 flex size-14 items-center justify-center rounded-2xl bg-white/80 text-foreground/80 shadow-sm backdrop-blur-sm">
                      <ArtworkIcon className="size-8" strokeWidth={1.6} />
                    </span>
                    <span className="absolute right-4 top-4 rounded-full bg-white/85 px-3 py-1 text-xs font-semibold text-foreground shadow-sm">
                      {template.seconds}s
                    </span>
                  </span>
                  <span className="flex flex-1 flex-col p-5">
                    <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">
                      {template.style}
                    </span>
                    <span className="mt-2 font-heading text-xl font-semibold leading-tight">
                      {template.title}
                    </span>
                    <span className="mt-2 text-sm leading-6 text-muted-foreground">
                      {template.preview}
                    </span>
                    <span className="mt-auto flex items-center justify-between border-t pt-4 text-sm font-semibold text-primary">
                      <span>Use this idea</span>
                      <ArrowUpRight
                        className="size-4 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                        aria-hidden="true"
                      />
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </section>
        {error && (
          <div
            role="alert"
            className="fixed bottom-4 right-4 z-50 max-w-md rounded-lg border border-destructive/30 bg-background p-4 text-sm text-destructive shadow-lg"
          >
            {error}
            <button className="ml-3 underline" onClick={() => setError("")}>
              Dismiss
            </button>
          </div>
        )}
        <span className="sr-only" role="status">
          {!loaded ? "Loading concepts" : announcement}
        </span>
      </main>
    );

  return (
    <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-[#fafaf9] text-foreground">
      <section className="flex min-h-0 flex-1 flex-col overflow-hidden" aria-label="Conversation">
        <div className="mx-auto flex h-full min-h-0 w-full max-w-3xl flex-col px-4 pb-4 pt-5 sm:px-6 sm:pb-6 sm:pt-6">
            <div
              ref={conversationScroll}
              className="min-h-0 flex-1 space-y-4 overflow-y-auto pb-4"
            >
              {visibleMessages.map((message, index) => {
                const newest = index === visibleMessages.length - 1;
                const isUser = message.role === "user";
                return (
                  <article
                    key={index}
                    ref={!isUser && newest ? latestReply : undefined}
                    tabIndex={!isUser && newest ? -1 : undefined}
                    className={
                      isUser
                        ? "ml-auto w-fit max-w-[min(85%,32rem)]"
                        : "max-w-[min(100%,42rem)]"
                    }
                  >
                    <div
                      className={`mb-2 flex items-center gap-2 text-xs font-semibold ${isUser ? "justify-end text-muted-foreground" : "text-primary"}`}
                    >
                      {!isUser && (
                        <span className="flex size-6 items-center justify-center rounded-full bg-primary/10">
                          <Sparkles className="size-3.5" />
                        </span>
                      )}
                      {isUser ? "You" : "Veyra assistant"}
                    </div>
                    {isUser && message.content.length > 360 ? (
                      <details className="rounded-2xl border bg-background px-3 py-2 shadow-sm">
                        <summary className="cursor-pointer text-sm font-medium leading-5">
                          {message.content.slice(0, 110).trimEnd()}…{" "}
                          <span className="text-primary">Read full idea</span>
                        </summary>
                        <p className="mt-2 whitespace-pre-wrap border-t pt-2 text-sm leading-5 text-muted-foreground">
                          {message.content}
                        </p>
                      </details>
                    ) : (
                      <div
                        className={`rounded-2xl text-sm whitespace-pre-wrap ${isUser ? "bg-primary px-3 py-2 leading-5 text-primary-foreground" : "border bg-background px-4 py-3 leading-6 shadow-sm"}`}
                      >
                        {message.content}
                      </div>
                    )}
                    {!isUser && message.question && (
                      <div className="mt-3 rounded-2xl border border-primary/20 bg-primary/[0.035] p-4 sm:p-5">
                        <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-primary">
                          <CircleHelp className="size-4" /> Your input
                        </div>
                        <p className="font-heading text-base font-semibold leading-6">
                          {message.question.prompt}
                        </p>
                        {newest && !hasStoryboard ? (
                          <div
                            className="mt-4 space-y-2"
                            role="group"
                            aria-label="Suggested answers"
                          >
                            {message.question.options.map((option) => (
                              <button
                                key={option.label}
                                type="button"
                                aria-pressed={selectedAnswer === option.label}
                                disabled={!!busy}
                                onClick={() => {
                                  setSelectedAnswer(option.label);
                                  setIdea("");
                                }}
                                className={`flex min-h-11 w-full flex-col rounded-xl border px-3 py-2.5 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${selectedAnswer === option.label ? "border-primary bg-primary/10" : "bg-background hover:border-primary/40 hover:bg-primary/5"}`}
                              >
                                <span className="font-medium">
                                  {option.label}
                                </span>
                                {option.description && (
                                  <span className="mt-0.5 text-xs leading-5 text-muted-foreground">
                                    {option.description}
                                  </span>
                                )}
                              </button>
                            ))}
                            <div className="flex justify-end pt-2">
                              <Button
                                type="button"
                                disabled={!selectedAnswer || !!busy}
                                onClick={() => void send(selectedAnswer)}
                              >
                                Continue <ArrowUpRight className="size-4" />
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <p className="mt-3 text-xs text-muted-foreground">
                            Answered in the next message
                          </p>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
              {hasStoryboard && (
                <section
                  ref={storyboardRef}
                  className="mt-6 space-y-4 rounded-2xl border bg-background p-4 shadow-sm sm:p-5"
                  aria-label="Storyboard and preview"
                >
                  {!draft && !concept?.scenes.length ? (
                    <div className="mx-auto flex max-w-sm flex-col items-center justify-center py-24 text-center">
                      <div className="flex size-12 items-center justify-center rounded-xl border bg-background">
                        <Film className="size-5 text-muted-foreground" />
                      </div>
                      <h2 className="mt-5 font-heading text-xl font-semibold">
                        Your storyboard will appear here
                      </h2>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        Once the concept is clear, review each scene, adjust the
                        prompts, and approve the sequence.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-widest text-primary">
                            Storyboard
                          </p>
                          <h2 className="mt-1 font-heading text-lg font-semibold">
                            {draft?.title ?? concept?.title}
                          </h2>
                        </div>
                        <span className="rounded-full border bg-background px-3 py-1 text-xs">
                          {total || concept?.target_seconds}s /{" "}
                          {concept?.target_seconds}s
                        </span>
                      </div>
                      {draft?.summary && (
                        <details className="text-sm text-muted-foreground">
                          <summary className="w-fit cursor-pointer font-medium text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
                            Story summary
                          </summary>
                          <p className="mt-2 leading-6">{draft.summary}</p>
                        </details>
                      )}
                      {concept?.status === "succeeded" && concept.video_url && (
                        <Card>
                          <CardContent className="space-y-3 p-4">
                            <video
                              controls
                              playsInline
                              preload="metadata"
                              src={concept.video_url}
                              className="w-full rounded-lg bg-black"
                              aria-label="Final video"
                            />
                            <a
                              href={concept.video_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-sm font-medium text-primary underline"
                            >
                              Download final video
                            </a>
                          </CardContent>
                        </Card>
                      )}
                      {(draft?.scenes ?? concept?.scenes ?? []).map((scene, index) => {
                        const generated = concept?.scenes[index];
                        const sceneStatus = generated?.job_status ?? generated?.status ?? "Planned";
                        return (
                          <Sheet key={index}>
                            <Card className="gap-0 rounded-xl py-0 shadow-none">
                              <CardContent className="flex items-center gap-3 p-3 sm:p-4">
                                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                                  {index + 1}
                                </span>
                                <div className="min-w-0 flex-1">
                                  <p className="truncate text-sm font-semibold">{scene.title}</p>
                                  <p className="mt-0.5 text-xs text-muted-foreground">{scene.duration_seconds}s · {sceneStatus}</p>
                                  <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">{scene.motion_prompt}</p>
                                </div>
                                <SheetTrigger aria-label={`View scene ${index + 1} details`} className="inline-flex min-h-10 shrink-0 items-center gap-1 rounded-lg border px-3 text-xs font-medium text-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
                                  Details <ChevronRight className="size-3.5" aria-hidden="true" />
                                </SheetTrigger>
                              </CardContent>
                            </Card>
                            <SheetContent className="w-full! max-w-lg! gap-0 overflow-y-auto p-0">
                              <SheetHeader className="border-b pr-12">
                                <SheetTitle>Scene {index + 1}: {scene.title}</SheetTitle>
                                <SheetDescription>{scene.duration_seconds} seconds · {sceneStatus}. {editing ? "Review and edit the scene before saving." : "Scene details and preview."}</SheetDescription>
                              </SheetHeader>
                              {generated?.video_url ? (
                                <video controls playsInline preload="metadata" src={generated.video_url} className="max-h-64 w-full bg-black" aria-label={`Scene ${index + 1} clip`} />
                              ) : generated?.image_url ? (
                                <div className="relative h-64 w-full bg-muted">
                                  <Image unoptimized fill sizes="(max-width: 640px) 100vw, 512px" src={generated.image_url} alt={`Scene ${index + 1} starting frame`} className="object-contain" />
                                </div>
                              ) : null}
                          <div className="space-y-4 p-4">
                                {editing && <div className="grid gap-3 sm:grid-cols-[1fr_110px]">
                                  <label className="grid gap-1 text-xs font-medium text-muted-foreground">
                                    Title
                                    <Input value={scene.title} disabled={!editing} maxLength={100}
                                      onChange={(event) => updateScene(index, { title: event.target.value })} />
                                  </label>
                                  <label className="grid gap-1 text-xs font-medium text-muted-foreground">
                                    Length
                                    <select value={scene.duration_seconds} disabled={!editing}
                                      onChange={(event) => updateScene(index, { duration_seconds: Number(event.target.value) })}
                                      className="h-9 rounded-md border bg-background px-2 text-sm text-foreground">
                                      <option value={5}>5 sec</option>
                                      <option value={10}>10 sec</option>
                                      <option value={20}>20 sec</option>
                                    </select>
                                  </label>
                                </div>}
                                <div className="grid gap-1 text-xs font-medium text-muted-foreground">
                                  <p>Starting image</p>
                                  {editing ? <Textarea aria-label={`Scene ${index + 1} starting image prompt`} value={scene.image_prompt} maxLength={2000} rows={6}
                                    onChange={(event) => updateScene(index, { image_prompt: event.target.value })} />
                                    : <span className="rounded-lg border bg-muted/40 p-3 text-sm font-normal leading-6 text-foreground">{scene.image_prompt}</span>}
                                </div>
                                <div className="grid gap-1 text-xs font-medium text-muted-foreground">
                                  <p>Motion and camera</p>
                                  {editing ? <Textarea aria-label={`Scene ${index + 1} motion and camera prompt`} value={scene.motion_prompt} maxLength={2000} rows={6}
                                    onChange={(event) => updateScene(index, { motion_prompt: event.target.value })} />
                                    : <span className="rounded-lg border bg-muted/40 p-3 text-sm font-normal leading-6 text-foreground">{scene.motion_prompt}</span>}
                                </div>
                            {generated?.job_error && <p className="text-xs text-destructive">{generated.job_error}</p>}
                          </div>
                          {editing && changed && (
                            <SheetFooter className="sticky bottom-0 border-t bg-popover">
                              <Button type="button" disabled={!!busy || total !== concept?.target_seconds} onClick={() => void savePlan()}>
                                {busy === "save" ? "Saving…" : "Save storyboard edits"}
                              </Button>
                              {total !== concept?.target_seconds && (
                                <p className="text-xs text-destructive">Scene lengths must total {concept?.target_seconds} seconds.</p>
                              )}
                            </SheetFooter>
                          )}
                        </SheetContent>
                          </Sheet>
                        );
                      })}
                      {editing && draft && (
                        <div className="rounded-xl border bg-background p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold">
                          Ready to make this video?
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {changed
                            ? "Save your scene edits to refresh the estimate."
                            : `Estimated cost: $${((concept.estimated_cost_cents ?? 0) / 100).toFixed(2)}.`}
                        </p>
                        <details className="mt-2 text-xs text-muted-foreground">
                          <summary className="w-fit cursor-pointer text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">How it works</summary>
                          <p className="mt-1 leading-5">We create an image and clip for each scene, then join the clips into one video.</p>
                        </details>
                            </div>
                            <div className="flex gap-2">
                              {changed && (
                                <Button
                                  variant="outline"
                                  disabled={
                                    !!busy || total !== concept?.target_seconds
                                  }
                                  onClick={() => void savePlan()}
                                >
                                  {busy === "save" ? "Saving…" : "Save edits"}
                                </Button>
                              )}
                              <Button
                                disabled={
                                  !!busy ||
                                  changed ||
                                  total !== concept?.target_seconds
                                }
                                onClick={() => setConfirmGeneration(true)}
                              >
                                <Check className="size-4" />{" "}
                                {busy === "generate"
                                  ? "Starting…"
                                  : "Approve & generate"}
                              </Button>
                            </div>
                          </div>
                          {total !== concept?.target_seconds && (
                            <p role="alert" className="mt-2 text-xs text-destructive">
                              Scene lengths must add up to {concept?.target_seconds}{" "}
                              seconds.
                            </p>
                          )}
                        </div>
                      )}
                      {concept?.status === "failed" && (
                        <div
                          role="alert"
                          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
                        >
                          <span>
                            Generation stopped:{" "}
                            {concept.error_code ?? "unknown error"}. Completed clips
                            remain available above. Retrying a clip may use more
                            credits.
                          </span>
                          <Button
                            variant="outline"
                            disabled={!!busy}
                            onClick={() => void retry()}
                          >
                            {busy === "retry" ? "Retrying…" : "Retry failed step"}
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                </section>
              )}
              {busy === "chat" && (
                <div
                  role="status"
                  className="flex items-center gap-2 text-sm text-muted-foreground"
                >
                  <Sparkles className="size-4 text-primary" /> Veyra is shaping
                  your story…
                </div>
              )}
            </div>
            {(editing || !concept) && (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  void send();
                }}
                className="mt-3 flex shrink-0 items-end gap-2 rounded-2xl border bg-background p-2 shadow-sm"
              >
                <Textarea
                  id="concept-chat-reply"
                  aria-label="Message the concept assistant"
                  value={idea}
                  disabled={busy === "chat"}
                  onChange={(event) => {
                    setIdea(event.target.value);
                    setSelectedAnswer("");
                  }}
                  maxLength={4000}
                  rows={1}
                  className="max-h-36 min-h-10 flex-1 resize-none overflow-y-auto border-0 px-2 shadow-none focus-visible:border-0 focus-visible:ring-0"
                  placeholder={
                    lastMessage?.role === "assistant" && !hasStoryboard
                      ? "Answer the question in your own words…"
                      : "Refine the story, style, or a scene…"
                  }
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                />
                <Button
                  type="submit"
                  size="icon-lg"
                  aria-label="Send message"
                  disabled={!idea.trim() || !!busy}
                  className="shrink-0 rounded-full"
                >
                  <ArrowUp className="size-4" />
                </Button>
              </form>
            )}
            {concept && !editing && (
              <p className="mt-6 rounded-xl border bg-muted px-4 py-3 text-sm text-muted-foreground">
                The approved plan is locked while clips are being generated.
              </p>
            )}
        </div>
      </section>
      <Dialog.Root open={confirmGeneration} onOpenChange={setConfirmGeneration}>
        <Dialog.Portal>
          <Dialog.Backdrop className="fixed inset-0 z-50 bg-black/40" />
          <Dialog.Popup className="fixed top-1/2 left-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border bg-background p-6 shadow-xl">
            <Dialog.Title className="font-heading text-lg font-semibold">
              Start video generation?
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm leading-6 text-muted-foreground">
              Approve the {concept?.target_seconds}-second storyboard. Estimated
              charge: ${((concept?.estimated_cost_cents ?? 0) / 100).toFixed(2)}.
              Images and clips are charged as they are created.
            </Dialog.Description>
            <div className="mt-6 flex justify-end gap-2">
              <Dialog.Close render={<Button variant="outline" />}>
                Cancel
              </Dialog.Close>
              <Button
                disabled={!!busy || changed || total !== concept?.target_seconds}
                onClick={() => {
                  setConfirmGeneration(false);
                  void generate();
                }}
              >
                Approve & generate
              </Button>
            </div>
          </Dialog.Popup>
        </Dialog.Portal>
      </Dialog.Root>
      {error && (
        <div
          role="alert"
          className="fixed bottom-4 right-4 z-50 max-w-md rounded-lg border border-destructive/30 bg-background p-4 text-sm text-destructive shadow-lg"
        >
          {error}
          <button className="ml-3 underline" onClick={() => setError("")}>
            Dismiss
          </button>
        </div>
      )}
      <span className="sr-only" role="status">
        {!loaded ? "Loading concepts" : announcement}
      </span>
    </main>
  );
}
