import Image from "next/image";
import { Clapperboard, PenLine, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { FadeIn } from "@/components/motion-primitives";

const steps = [
  { icon: PenLine, title: "Describe or upload", body: "Write a one-line idea, or drop in an image to animate. Image-to-video uses your picture as the opening frame." },
  { icon: Sparkles, title: "Refine with the creative agent", body: "A Gemini agent turns your idea into a model-aware prompt for $0.02, or generates and edits a scene image for $0.20." },
  { icon: Clapperboard, title: "Quote, generate, keep", body: "See the exact price before you confirm. Finished clips stay in your library, and failed jobs refund automatically." },
];

export function HowItWorks() {
  return <FadeIn>
    <section id="how-it-works" className="scroll-mt-24 space-y-6" aria-labelledby="how-title">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-600">How it works</p>
        <h2 id="how-title" className="mt-1 text-3xl font-semibold tracking-tight">Three steps from idea to clip.</h2>
      </div>
      <ol className="grid gap-4 sm:grid-cols-3">
        {steps.map((step, index) => <li key={step.title}>
          <FadeIn delay={index * 0.08}>
            <div className="h-full rounded-2xl border bg-card p-5 shadow-sm">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
                <step.icon className="h-4.5 w-4.5" aria-hidden="true" />
              </span>
              <h3 className="mt-3 text-lg font-semibold"><span className="mr-2 text-sm font-semibold text-violet-600">{String(index + 1).padStart(2, "0")}</span>{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
            </div>
          </FadeIn>
        </li>)}
      </ol>
    </section>
  </FadeIn>;
}

// Settings and prices mirror src/config.py (MODEL_PROFILES, VIDEO_BASE_PRICES_CENTS).
const models = [
  { id: "ltx-2.3-distilled", name: "LTX 2.3 Distilled", poster: "robot-garden", alt: "Frame of a 3D animated robot garden", modes: "Text and image to video", lengths: "5, 10, or 20 seconds", quality: "512p · 24 fps", price: "From $0.25", tag: "Most flexible" },
  { id: "wan-2.2", name: "Wan 2.2", poster: "clay-astronaut", alt: "Frame of a clay-animated astronaut", modes: "Text to video", lengths: "5 seconds", quality: "720p", price: "From $0.45", tag: "Sharpest detail" },
  { id: "hunyuanvideo-1.5", name: "HunyuanVideo 1.5", poster: "watercolor-koi", alt: "Frame of a watercolor koi painting", modes: "Text to video", lengths: "5 seconds", quality: "480p", price: "From $0.35", tag: "Painterly looks" },
  { id: "cogvideox-1.5", name: "CogVideoX 1.5", poster: "knitted-whale", alt: "Frame of a knitted whale in stop motion", modes: "Text to video", lengths: "5 seconds", quality: "480p", price: "From $0.35", tag: "Stylized motion" },
];

export function ModelLineup() {
  return <section className="space-y-6" aria-labelledby="models-title">
    <FadeIn>
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-600">Model lineup</p>
        <h2 id="models-title" className="mt-1 text-3xl font-semibold tracking-tight">Pick the engine that fits the look.</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground sm:text-base">
          Every frame below comes from a real clip made with that model through this API. Prices are per clip,
          and the exact quote always appears before you confirm a charge.
        </p>
      </div>
    </FadeIn>
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {models.map((model, index) => <FadeIn key={model.id} delay={index * 0.06}>
        <motion.article whileHover={{ y: -6 }} transition={{ type: "spring", stiffness: 300, damping: 22 }}
          className="group h-full overflow-hidden rounded-2xl border bg-card shadow-sm">
          <div className="relative aspect-video bg-slate-950">
            <Image src={`/videos/${model.poster}.jpg`} alt={model.alt} fill
              sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
              className="object-cover transition-transform duration-500 group-hover:scale-105" />
            <span className="absolute left-3 top-3 rounded-full bg-slate-950/80 px-2.5 py-1 text-[11px] font-medium text-white">{model.tag}</span>
          </div>
          <div className="space-y-2 p-4">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-base font-semibold">{model.name}</h3>
              <span className="whitespace-nowrap rounded-full bg-muted px-2.5 py-1 text-[11px] text-muted-foreground">{model.price}</span>
            </div>
            <p className="text-sm text-muted-foreground">{model.modes} · {model.lengths}</p>
            <p className="text-xs text-muted-foreground">{model.quality}</p>
          </div>
        </motion.article>
      </FadeIn>)}
    </div>
  </section>;
}

const marqueeSlugs = [
  "paper-city", "clay-astronaut", "watercolor-koi", "robot-garden", "balloon-voyage",
  "pixel-train", "ink-fox", "knitted-whale", "isometric-market", "glass-butterfly",
];

export function PosterMarquee() {
  return <FadeIn>
    <div className="marquee-hover overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]"
      aria-label="Preview strip of every demo style, scrolling; links to the gallery">
      <div className="flex w-max gap-4 animate-marquee motion-reduce:animate-none">
        {[...marqueeSlugs, ...marqueeSlugs].map((slug, index) => {
          const duplicate = index >= marqueeSlugs.length;
          return <a key={`${slug}-${index}`} href="#showcase" tabIndex={duplicate ? -1 : 0} aria-hidden={duplicate || undefined}
            className="group relative block w-40 shrink-0 overflow-hidden rounded-xl border bg-card shadow-sm sm:w-48">
            <span className="relative block aspect-video bg-slate-950">
              <Image src={`/videos/${slug}.jpg`} alt="" fill sizes="192px"
                className="object-cover transition-transform duration-500 group-hover:scale-110" />
            </span>
          </a>;
        })}
      </div>
    </div>
  </FadeIn>;
}
