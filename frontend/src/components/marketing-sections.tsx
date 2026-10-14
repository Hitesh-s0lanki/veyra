import Image from "next/image";
import { Clapperboard, Cpu, ExternalLink, Layers3, PenLine } from "lucide-react";
import { motion } from "motion/react";
import { FadeIn } from "@/components/motion-primitives";

const steps = [
  { icon: PenLine, title: "Bring an idea", body: "Write a prompt, or give LTX 2.3 an image to animate." },
  { icon: Layers3, title: "Choose a model", body: "Try a different engine to find the motion and style you want." },
  { icon: Clapperboard, title: "Run a real render", body: "Review the price, generate on a Modal GPU worker, and keep the MP4 in your library." },
];

// Keep this overview aligned with the enabled MODEL_PROFILES in src/config.py.
const openModels = [
  { name: "LTX 2.3 Distilled", capability: "Text + image to video" },
  { name: "Wan 2.2", capability: "Text to video" },
  { name: "HunyuanVideo 1.5", capability: "Text to video" },
  { name: "CogVideoX 1.5", capability: "Text to video" },
];

export function HowItWorks() {
  return <div id="how-it-works" className="scroll-mt-24 space-y-5">
    <div className="relative isolate overflow-hidden rounded-[1.75rem] bg-[#171b36] p-6 text-white sm:p-8 lg:p-10">
      <div aria-hidden="true" className="pointer-events-none absolute -right-16 -top-24 -z-10 h-72 w-72 rounded-full bg-[#6759e8]/35 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-32 left-1/4 -z-10 h-64 w-64 rounded-full bg-[#2682b5]/20 blur-3xl" />
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)] lg:items-center lg:gap-12">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-semibold text-[#d9dbff]"><Cpu size={15} aria-hidden="true" /> On-demand GPU workers</span>
          <h3 className="mt-5 max-w-lg font-heading text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">Meet the engines behind the motion.</h3>
          <p className="mt-3 max-w-lg text-sm leading-relaxed text-[#c7c9df] sm:text-base">This project sends generation jobs to four separately deployed Modal GPU workers. Pick an engine, test an idea, and keep the resulting MP4 in your library.</p>
          <a href="https://github.com/Hitesh-s0lanki/video-generation-pipeline" target="_blank" rel="noopener noreferrer" className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-white underline decoration-white/40 underline-offset-4 transition hover:decoration-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white">Explore the source <ExternalLink size={17} aria-hidden="true" /><span className="sr-only">(opens in a new tab)</span></a>
        </div>
        <div className="grid grid-cols-1 gap-2.5 min-[480px]:grid-cols-2 sm:gap-3" aria-label="Available video models">
          {openModels.map((model, index) => <div key={model.name} className="min-h-27 rounded-2xl border border-white/15 bg-white/10 p-3.5 backdrop-blur-sm sm:p-4">
            <span className="text-[11px] font-bold tracking-[0.18em] text-[#aaa8ff]">0{index + 1}</span>
            <p className="mt-2 font-heading text-sm font-semibold leading-tight text-white sm:text-base">{model.name}</p>
            <p className="mt-1 text-xs leading-snug text-[#c7c9df]">{model.capability}</p>
          </div>)}
        </div>
      </div>
    </div>
    <div className="rounded-2xl bg-[#f2f2fb] px-5 py-6 sm:px-7 sm:py-7">
      <h3 className="mb-5 text-xs font-bold uppercase tracking-[0.17em] text-[#5752ad]">How a clip gets made</h3>
      <ol className="grid gap-6 md:grid-cols-3 md:gap-0" aria-label="How video creation works">
        {steps.map((step, index) => <li key={step.title} className="flex gap-4 md:flex-col md:gap-3 md:border-r md:border-[#dcdcef] md:px-6 md:first:pl-0 md:last:border-r-0 md:last:pr-0">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white text-[#514ad5] shadow-sm" aria-hidden="true">
            <step.icon className="h-5 w-5" strokeWidth={1.8} />
          </span>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#5854b4]">Step {String(index + 1).padStart(2, "0")}</p>
            <h4 className="mt-1 font-heading text-base font-semibold leading-snug text-[#1b1b26] sm:text-lg">{step.title}</h4>
            <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-[#58586a]">{step.body}</p>
          </div>
        </li>)}
      </ol>
    </div>
  </div>;
}

// Settings and prices mirror src/config.py (MODEL_PROFILES, VIDEO_BASE_PRICES_CENTS).
const models = [
  { id: "ltx-2.3-distilled", name: "LTX 2.3 Distilled", poster: "robot-garden", alt: "Frame of a 3D animated robot garden", modes: "Text and image to video", lengths: "5, 10, or 20 seconds", quality: "512p · 24 fps", price: "From $0.45", tag: "Most flexible" },
  { id: "wan-2.2", name: "Wan 2.2", poster: "clay-astronaut", alt: "Frame of a clay-animated astronaut", modes: "Text to video", lengths: "5 seconds", quality: "720p", price: "From $0.65", tag: "Sharpest detail" },
  { id: "hunyuanvideo-1.5", name: "HunyuanVideo 1.5", poster: "watercolor-koi", alt: "Frame of a watercolor koi painting", modes: "Text to video", lengths: "5 seconds", quality: "480p", price: "From $0.55", tag: "Painterly looks" },
  { id: "cogvideox-1.5", name: "CogVideoX 1.5", poster: "knitted-whale", alt: "Frame of a knitted whale in stop motion", modes: "Text to video", lengths: "5 seconds", quality: "480p", price: "From $0.55", tag: "Stylized motion" },
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
