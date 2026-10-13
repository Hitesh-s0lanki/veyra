"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ArrowUpRight, Pause, Play } from "lucide-react";

const featured = [
  { slug: "ink-fox", title: "Ink Fox", style: "Ink painting" },
  { slug: "neon-jellyfish", title: "Neon Jellyfish", style: "Dreamscape" },
  { slug: "origami-dragon", title: "Origami Dragon", style: "Featured film" },
  { slug: "paper-city", title: "Paper City", style: "Paper craft" },
  { slug: "clay-astronaut", title: "Clay Astronaut", style: "Clay animation" },
] as const;

function HeroClip({ clip, featuredClip }: { clip: typeof featured[number]; featuredClip: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [failed, setFailed] = useState(false);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!featuredClip) return;
    const video = ref.current;
    if (!video) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let visible = false;
    const sync = () => {
      if (visible && !document.hidden && !reduced.matches) {
        void video.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
      } else {
        video.pause();
        setPlaying(false);
      }
    };
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      sync();
    }, { threshold: 0.25 });
    observer.observe(video);
    document.addEventListener("visibilitychange", sync);
    reduced.addEventListener("change", sync);
    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", sync);
      reduced.removeEventListener("change", sync);
      video.pause();
    };
  }, [featuredClip]);

  function togglePlayback() {
    const video = ref.current;
    if (!video) return;
    if (video.paused) void video.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    else { video.pause(); setPlaying(false); }
  }

  return <article className="hero-fan-card" aria-hidden={!featuredClip}>
    {!featuredClip || failed ? <Image src={`/videos/${clip.slug}.jpg`} alt={featuredClip ? `${clip.title} video preview` : ""} fill sizes={featuredClip ? "(max-width: 767px) 42vw, 290px" : "220px"} className="hero-fan-media" /> :
      <video ref={ref} className="hero-fan-media" poster={`/videos/${clip.slug}.jpg`} muted loop playsInline preload={featuredClip ? "metadata" : "none"} onError={() => setFailed(true)} aria-label={`${clip.title} animated video`}>
        <source src={`/videos/${clip.slug}.mp4`} type="video/mp4" />
      </video>}
    <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-black/10" />
    {featuredClip && <button type="button" onClick={togglePlayback} disabled={failed} aria-label={`${playing ? "Pause" : "Play"} ${clip.title}`} className="absolute right-3 top-3 flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border border-white/40 bg-black/35 text-white backdrop-blur-sm transition hover:bg-black/65 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white disabled:opacity-50">
      {playing ? <Pause size={17} fill="currentColor" aria-hidden="true" /> : <Play size={17} fill="currentColor" aria-hidden="true" />}
    </button>}
    <div className="hero-fan-label pointer-events-none absolute inset-x-0 bottom-0 p-4 text-white sm:p-5">
      <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-white/80">{clip.style}</p>
      <p className="mt-1 font-heading text-base font-semibold leading-tight sm:text-xl">{clip.title}</p>
    </div>
  </article>;
}

export function HeroReel() {
  return <section className="relative overflow-hidden rounded-[2rem] bg-[#f0f1ec] px-4 pb-0 pt-10 text-[#171a19] sm:px-8 sm:pt-14" aria-labelledby="hero-title">
    <div className="relative z-10 mx-auto max-w-3xl text-center">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#4a56a8]">Imagine it. See it move.</p>
      <h1 id="hero-title" className="mt-3 font-heading text-[clamp(2.6rem,5vw,5rem)] font-semibold leading-[1.02] tracking-[-0.065em]">
        Make something <span className="text-[#5a55df]">move.</span>
      </h1>
      <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-[#565e52] sm:text-lg">
        Create expressive videos from a prompt or image. Every scene below started with an idea.
      </p>
      <a href="#create" className="mt-6 inline-flex min-h-12 items-center gap-2 rounded-full bg-primary px-7 text-sm font-bold text-primary-foreground shadow-lg shadow-black/10 transition hover:bg-primary/80 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary">
        Get started <ArrowUpRight size={18} aria-hidden="true" />
      </a>
    </div>
    <div className="hero-fan mx-auto mt-8" aria-label="Featured videos">
      {featured.map((clip, index) => <HeroClip key={clip.slug} clip={clip} featuredClip={index === 2} />)}
    </div>
  </section>;
}
