import { Globe2, Mail } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

function GithubIcon() {
  return <svg viewBox="0 0 24 24" fill="currentColor" className="size-4" aria-hidden="true"><path d="M12 .297a12 12 0 0 0-3.793 23.385c.6.112.82-.26.82-.578 0-.284-.01-1.04-.015-2.04-3.338.726-4.043-1.61-4.043-1.61-.546-1.387-1.333-1.757-1.333-1.757-1.09-.745.083-.73.083-.73 1.205.086 1.84 1.237 1.84 1.237 1.07 1.835 2.807 1.305 3.492.998.108-.775.418-1.305.762-1.604-2.665-.303-5.467-1.333-5.467-5.932 0-1.31.468-2.38 1.235-3.22-.124-.303-.535-1.523.117-3.176 0 0 1.008-.323 3.3 1.23a11.5 11.5 0 0 1 6 0c2.29-1.553 3.296-1.23 3.296-1.23.654 1.653.243 2.873.12 3.176.77.84 1.234 1.91 1.234 3.22 0 4.61-2.806 5.625-5.48 5.921.43.372.823 1.102.823 2.222 0 1.606-.014 2.896-.014 3.286 0 .32.216.695.825.577A12.001 12.001 0 0 0 12 .297Z" /></svg>;
}

function LinkedinIcon() {
  return <svg viewBox="0 0 24 24" fill="currentColor" className="size-4" aria-hidden="true"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286ZM5.337 7.433a2.062 2.062 0 1 1 0-4.125 2.062 2.062 0 0 1 0 4.125Zm1.782 13.019H3.555V9h3.564v11.452ZM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.225 0Z" /></svg>;
}

const socialLinks = [
  { label: "Hitesh Solanki's website", href: "https://hiteshsolanki.com", Icon: Globe2 },
  { label: "Veyra source on GitHub", href: "https://github.com/Hitesh-s0lanki/video-generation-pipeline", Icon: GithubIcon },
  { label: "Hitesh Solanki on LinkedIn", href: "https://www.linkedin.com/in/hitesh-solanki", Icon: LinkedinIcon },
  { label: "Email Hitesh Solanki", href: "mailto:hiteshsolanki4623@gmail.com", Icon: Mail },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-white/10 bg-[#0b0e16] text-[#c9d0e0]">
      <div className="mx-auto w-full max-w-[1500px] px-4 py-12 sm:px-6 sm:py-14 lg:px-10">
        <div className="flex flex-col gap-10 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-xs">
            <Link
              href="/"
              className="inline-flex items-center gap-3 rounded-sm text-[#f3f5fa] outline-none focus-visible:ring-2 focus-visible:ring-[#8c83ff] focus-visible:ring-offset-4 focus-visible:ring-offset-[#0b0e16]"
              aria-label="Veyra home"
            >
              <Image src="/veyra-mark.png" alt="" width={446} height={445} className="h-12 w-12 object-contain" />
              <span className="font-heading text-2xl font-semibold tracking-tight">Veyra</span>
            </Link>
            <p className="mt-3 text-sm leading-relaxed text-[#a8b1c6]">
              Imagine it. See it move. Create AI videos from text and images.
            </p>
          </div>

          <div className="sm:text-right">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#a8b1c6]">Built by</p>
            <a
              href="https://hiteshsolanki.com"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1.5 inline-block rounded-sm font-heading text-2xl font-bold tracking-[-0.04em] text-[#f3f5fa] underline-offset-[6px] outline-none hover:underline focus-visible:ring-2 focus-visible:ring-[#8c83ff] focus-visible:ring-offset-4 focus-visible:ring-offset-[#0b0e16]"
            >
              Hitesh Solanki
            </a>
            <ul className="mt-4 flex flex-wrap items-center gap-2 sm:justify-end" aria-label="Creator links">
              {socialLinks.map(({ label, href, Icon }) => (
                <li key={href}>
                  <a
                    href={href}
                    aria-label={label}
                    target={href.startsWith("mailto:") ? undefined : "_blank"}
                    rel={href.startsWith("mailto:") ? undefined : "noopener noreferrer"}
                    className="flex size-11 items-center justify-center rounded-full border border-white/20 text-[#c9d0e0] outline-none transition-colors hover:border-[#8c83ff] hover:bg-white/10 hover:text-white focus-visible:ring-2 focus-visible:ring-[#8c83ff] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0b0e16]"
                  >
                    <Icon className="size-4" aria-hidden="true" />
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col-reverse gap-4 border-t border-white/10 pt-6 text-xs text-[#a8b1c6] sm:flex-row sm:items-center sm:justify-between">
          <p>© Hitesh Solanki</p>
          <nav aria-label="Footer navigation" className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <Link href="/#showcase" className="rounded-sm hover:text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#8c83ff]">Explore</Link>
            <Link href="/#create" className="rounded-sm hover:text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#8c83ff]">Studio</Link>
            <Link href="/mcp" className="rounded-sm hover:text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#8c83ff]">MCP</Link>
          </nav>
        </div>
      </div>
    </footer>
  );
}
