"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ArrowLeft, ArrowRight, Download, Pause, Play, Volume2, VolumeX } from "lucide-react";

const clips = [
  ["origami-dragon", "Origami Dragon", "Paper art"],
  ["neon-jellyfish", "Neon Jellyfish", "Bioluminescent"],
  ["chalk-village", "Chalk Village", "Pastel world"],
  ["felt-campfire", "Felt Campfire", "Stop motion"],
  ["toy-carousel", "Toy Carousel", "Wooden miniature"],
  ["paper-city", "Paper City", "Paper craft"],
  ["clay-astronaut", "Clay Astronaut", "Clay animation"],
  ["watercolor-koi", "Watercolor Koi", "Watercolor"],
  ["robot-garden", "Robot Garden", "3D animation"],
  ["balloon-voyage", "Balloon Voyage", "Storybook"],
  ["pixel-train", "Pixel Train", "Pixel art"],
  ["ink-fox", "Ink Fox", "Ink painting"],
  ["knitted-whale", "Knitted Whale", "Textile art"],
  ["isometric-market", "Isometric Market", "Miniature 3D"],
  ["glass-butterfly", "Glass Butterfly", "Glass art"],
] as const;

function VideoTile({ clip, index }: { clip: typeof clips[number]; index: number }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [failed, setFailed] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(true);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let inView = false;
    const syncPlayback = () => {
      if (inView && !reduced.matches && !document.hidden) {
        void video.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
      } else {
        video.pause();
        setPlaying(false);
      }
    };
    const observer = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      syncPlayback();
    }, { threshold: 0.55 });
    observer.observe(video);
    document.addEventListener("visibilitychange", syncPlayback);
    reduced.addEventListener("change", syncPlayback);
    return () => { observer.disconnect(); document.removeEventListener("visibilitychange", syncPlayback); reduced.removeEventListener("change", syncPlayback); video.pause(); };
  }, []);

  function togglePlayback() {
    const video = ref.current;
    if (!video) return;
    if (video.paused) void video.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    else { video.pause(); setPlaying(false); }
  }

  return <article className={`showcase-tile showcase-tile-${index % 5} group relative shrink-0 overflow-hidden rounded-[1.25rem] bg-[#24252a]`}>
    <div className="relative h-full">
      {failed ? <Image src={`/videos/${clip[0]}.jpg`} alt={`${clip[1]} video preview`} fill sizes="(max-width: 640px) 78vw, 420px" className="object-cover" /> :
        <video ref={ref} className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-[1.04]" poster={`/videos/${clip[0]}.jpg`} muted={muted} loop playsInline preload="none" onError={() => setFailed(true)} aria-label={`${clip[1]} animated video`}>
          <source src={`/videos/${clip[0]}.mp4`} type="video/mp4" />
        </video>}
      <a href={`/videos/${clip[0]}.mp4`} download={`${clip[0]}.mp4`} aria-label={`Download ${clip[1]} video`} className="absolute right-3 top-3 z-10 flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border border-white/45 bg-black/40 text-white backdrop-blur-sm transition hover:bg-black/65 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"><Download size={17} aria-hidden="true" /></a>
      <div className="showcase-tile-details absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 bg-gradient-to-t from-black/85 via-black/35 to-transparent p-4 pt-12 text-white">
        <div className="min-w-0 pb-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/80">{clip[2]}</p>
          <h3 className="mt-1 truncate text-base font-semibold tracking-tight sm:text-lg">{clip[1]}</h3>
        </div>
        <div className="flex shrink-0 gap-2">
          <button type="button" onClick={togglePlayback} disabled={failed} aria-label={`${playing ? "Pause" : "Play"} ${clip[1]}`} className="flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border border-white/45 bg-black/35 text-white backdrop-blur-sm transition hover:bg-black/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white disabled:opacity-50">{playing ? <Pause size={17} fill="currentColor" aria-hidden="true" /> : <Play size={17} fill="currentColor" aria-hidden="true" />}</button>
          <button type="button" onClick={() => setMuted((value) => !value)} disabled={failed} aria-label={`${muted ? "Unmute" : "Mute"} ${clip[1]}`} className="flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border border-white/45 bg-black/35 text-white backdrop-blur-sm transition hover:bg-black/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white disabled:opacity-50">{muted ? <VolumeX size={17} aria-hidden="true" /> : <Volume2 size={17} aria-hidden="true" />}</button>
        </div>
      </div>
    </div>
  </article>;
}

export function VideoShowcase() {
  const railRef = useRef<HTMLDivElement>(null);
  const [canScrollBack, setCanScrollBack] = useState(false);
  const [canScrollForward, setCanScrollForward] = useState(true);

  useEffect(() => {
    const rail = railRef.current;
    if (!rail) return;
    const updateControls = () => {
      setCanScrollBack(rail.scrollLeft > 2);
      setCanScrollForward(rail.scrollLeft < rail.scrollWidth - rail.clientWidth - 2);
    };
    const resizeObserver = new ResizeObserver(updateControls);
    resizeObserver.observe(rail);
    rail.addEventListener("scroll", updateControls, { passive: true });
    updateControls();
    return () => {
      resizeObserver.disconnect();
      rail.removeEventListener("scroll", updateControls);
    };
  }, []);

  function moveGallery(direction: -1 | 1) {
    const rail = railRef.current;
    if (!rail) return;
    rail.scrollBy({ left: direction * Math.min(rail.clientWidth * 0.8, 620), behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }

  return <section id="showcase" className="scroll-mt-24 space-y-6" aria-labelledby="showcase-title">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-600">Explore the possibilities</p>
        <h2 id="showcase-title" className="mt-1 font-heading text-3xl font-semibold tracking-tight sm:text-4xl">Made to move.</h2>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground sm:text-base">Browse real clips in a range of styles. Play, listen, or download a favorite.</p>
      </div>
      <div className="flex gap-2">
        <button type="button" onClick={() => moveGallery(-1)} disabled={!canScrollBack} aria-label="Previous videos" aria-controls="showcase-rail" className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-white text-foreground transition hover:border-primary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-40"><ArrowLeft size={18} aria-hidden="true" /></button>
        <button type="button" onClick={() => moveGallery(1)} disabled={!canScrollForward} aria-label="Next videos" aria-controls="showcase-rail" className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-white text-foreground transition hover:border-primary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-40"><ArrowRight size={18} aria-hidden="true" /></button>
      </div>
    </div>
    <div id="showcase-rail" ref={railRef} className="showcase-rail flex gap-3 overflow-x-auto pb-3 sm:gap-4" role="region" aria-label="Video gallery. Scroll horizontally to explore more videos." tabIndex={0}>
      {clips.map((clip, index) => <VideoTile key={clip[0]} clip={clip} index={index} />)}
    </div>
  </section>;
}
