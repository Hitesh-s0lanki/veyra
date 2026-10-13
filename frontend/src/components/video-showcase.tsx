"use client";

import { useEffect, useRef, useState } from "react";
import { Download, Pause, Play, Volume2, VolumeX } from "lucide-react";

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

const tileWidths = [
  "clamp(180px, 14vw, 230px)",
  "clamp(430px, 39vw, 700px)",
  "clamp(180px, 14vw, 230px)",
  "clamp(300px, 24vw, 420px)",
  "clamp(180px, 14vw, 230px)",
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

  return <article className={`showcase-tile showcase-tile-${index % 5} group relative shrink-0 overflow-hidden rounded-[1.25rem] bg-[#24252a]`} style={{ width: tileWidths[index % tileWidths.length], height: "clamp(300px, 27vw, 400px)", scrollSnapAlign: "start" }}>
    <div className="relative h-full">
      {failed ? <img src={`/videos/${clip[0]}.jpg`} alt={`${clip[1]} video preview`} className="absolute inset-0 h-full w-full object-cover" /> :
        <video ref={ref} className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-[1.04]" poster={`/videos/${clip[0]}.jpg`} muted={muted} loop playsInline preload="none" onError={() => setFailed(true)} aria-label={`${clip[1]} animated video`}>
          <source src={`/videos/${clip[0]}.mp4`} type="video/mp4" />
          <img src={`/videos/${clip[0]}.jpg`} alt={`${clip[1]} video preview`} />
        </video>}
      <a href={`/videos/${clip[0]}.mp4`} download={`${clip[0]}.mp4`} aria-label={`Download ${clip[1]} video`} className="absolute right-3 top-3 z-10 flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border border-white/45 bg-black/40 text-white backdrop-blur-sm transition hover:bg-black/65 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"><Download size={17} aria-hidden="true" /></a>
      <div className="showcase-tile-details absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 bg-gradient-to-t from-black/70 via-black/20 to-transparent p-4 text-white">
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
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    const rail = railRef.current;
    if (!rail || !autoScroll) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let visible = false;
    let hovered = false;
    let focused = false;
    let pauseUntil = 0;
    let direction = 1;
    let previousTime = 0;
    let frame = 0;

    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; }, { threshold: 0.15 });
    observer.observe(rail);

    const pauseForInteraction = () => { pauseUntil = performance.now() + 5000; };
    const onMouseEnter = () => { hovered = true; };
    const onMouseLeave = () => { hovered = false; };
    const onFocusIn = () => { focused = true; };
    const onFocusOut = (event: FocusEvent) => {
      if (!rail.contains(event.relatedTarget as Node | null)) focused = false;
    };
    rail.addEventListener("mouseenter", onMouseEnter);
    rail.addEventListener("mouseleave", onMouseLeave);
    rail.addEventListener("focusin", onFocusIn);
    rail.addEventListener("focusout", onFocusOut);
    rail.addEventListener("pointerdown", pauseForInteraction);
    rail.addEventListener("wheel", pauseForInteraction, { passive: true });

    const tick = (time: number) => {
      const elapsed = Math.min(time - (previousTime || time), 64);
      previousTime = time;
      if (visible && !hovered && !focused && time >= pauseUntil && !document.hidden && !reducedMotion.matches) {
        const limit = rail.scrollWidth - rail.clientWidth;
        if (limit > 0) {
          rail.scrollLeft += direction * 52 * elapsed / 1000;
          if (rail.scrollLeft >= limit - 1) direction = -1;
          else if (rail.scrollLeft <= 1) direction = 1;
        }
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      rail.removeEventListener("mouseenter", onMouseEnter);
      rail.removeEventListener("mouseleave", onMouseLeave);
      rail.removeEventListener("focusin", onFocusIn);
      rail.removeEventListener("focusout", onFocusOut);
      rail.removeEventListener("pointerdown", pauseForInteraction);
      rail.removeEventListener("wheel", pauseForInteraction);
    };
  }, [autoScroll]);

  return <section id="showcase" className="showcase-section scroll-mt-24" style={{ position: "relative", left: "50%", width: "100vw", transform: "translateX(-50%)", overflow: "hidden", paddingBlock: "2rem 2.5rem" }} aria-label="Video gallery">

    <button type="button" onClick={() => setAutoScroll((current) => !current)} aria-label={`${autoScroll ? "Pause" : "Resume"} gallery scrolling`} aria-pressed={!autoScroll} className="absolute z-10 flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border border-[#d8d8d2] bg-white/90 text-[#151515] transition hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#5a55df]" style={{ position: "absolute", right: 16, top: 8, zIndex: 10 }}>{autoScroll ? <Pause size={18} aria-hidden="true" /> : <Play size={18} aria-hidden="true" />}</button>
    <div ref={railRef} className="showcase-rail mt-10 flex gap-3 overflow-x-auto px-4 pb-2 sm:mt-14 sm:gap-4 sm:px-6 lg:px-10" style={{ scrollbarWidth: "none", scrollSnapType: "none", overscrollBehaviorX: "contain" }} role="region" aria-label="Video gallery. Scroll horizontally to explore more videos." tabIndex={0}>
      {clips.map((clip, index) => <VideoTile key={clip[0]} clip={clip} index={index} />)}
    </div>
  </section>;
}
