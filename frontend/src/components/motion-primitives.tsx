"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";

/** Fade-and-rise reveal when the element scrolls into view. Runs once. */
export function FadeIn({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return <motion.div className={className}
    initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true, margin: "-64px" }}
    transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1], delay }}>
    {children}
  </motion.div>;
}
