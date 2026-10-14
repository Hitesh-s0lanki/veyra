"use client";

import { HeroReel } from "@/components/hero-reel";
import { VideoShowcase } from "@/components/video-showcase";
import { HowItWorks, ModelLineup } from "@/components/marketing-sections";

export default function Home() {
  return (
    <main className="mx-auto flex w-full flex-1 flex-col gap-14 px-4 py-6 sm:gap-20 sm:px-6 sm:py-10 lg:px-20">
      <HeroReel />
      <VideoShowcase />
      <HowItWorks />
      <ModelLineup />
    </main>
  );
}
