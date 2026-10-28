import type { ReactNode } from "react";

export const REPO_URL = "https://github.com/jessecalvin08/forkfix";

const LINKS = [
  { label: "How", href: "#method" },
  { label: "Evidence", href: "#evidence" },
  { label: "Replay", href: "#replay" },
  { label: "Issues", href: "#real-issues" },
];

export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-rule bg-paper/95 backdrop-blur-sm">
      <div className="wrap flex h-14 items-center justify-between gap-4">
        <a href="#top" className="flex min-h-11 min-w-9 items-center gap-2 font-semibold tracking-tight">
          <img src="/forkfix-mark.svg" alt="" width={20} height={20} />
          <span className="max-sm:sr-only">Forkfix</span>
        </a>
        <nav aria-label="Sections" className="flex items-center text-sm sm:gap-1">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="inline-flex min-h-11 items-center rounded-sm px-1.5 text-muted transition-colors hover:text-ink sm:px-2.5"
            >
              {l.label}
            </a>
          ))}
          <a
            href={REPO_URL}
            className="inline-flex min-h-11 items-center rounded-sm px-2 font-medium sm:ml-1 sm:px-3 underline decoration-rule-strong underline-offset-4 transition-colors hover:decoration-accent"
          >
            Source
          </a>
        </nav>
      </div>
    </header>
  );
}

/**
 * A section. `stack` puts the heading above the content (the workbenches need the width);
 * otherwise the heading stays in a left column while the content scrolls past it.
 */
export function Section({
  id,
  anchor,
  title,
  lede,
  stack = false,
  band = false,
  children,
}: {
  id: string;
  anchor?: string;
  title: string;
  lede?: ReactNode;
  stack?: boolean;
  band?: boolean;
  children: ReactNode;
}) {
  const heading = (
    <div className={stack ? "max-w-[62ch]" : "md:sticky md:top-24 md:self-start"}>
      <h2
        id={id}
        className={`font-semibold leading-[1.12] tracking-[-0.025em] ${
          stack ? "text-[clamp(1.6rem,1.1rem+1.8vw,2.4rem)]" : "text-[clamp(1.45rem,1.1rem+1vw,1.85rem)]"
        }`}
      >
        {title}
      </h2>
      {lede ? <p className="mt-3 text-muted">{lede}</p> : null}
    </div>
  );
  return (
    <section id={anchor} aria-labelledby={id} className={`border-t border-rule py-14 md:py-20 ${band ? "band" : ""}`}>
      <div className="wrap">
        {stack ? (
          <>
            {heading}
            <div className="mt-10">{children}</div>
          </>
        ) : (
          <div className="grid gap-x-12 gap-y-8 md:grid-cols-[260px_minmax(0,1fr)]">
            {heading}
            <div className="min-w-0">{children}</div>
          </div>
        )}
      </div>
    </section>
  );
}

const LINK = "inline-flex min-h-9 items-center underline underline-offset-4 hover:text-accent";

export function Footer() {
  return (
    <footer className="border-t border-rule">
      <div className="wrap grid gap-10 py-12 text-sm md:grid-cols-[260px_minmax(0,1fr)] md:gap-12">
        <div>
          <p className="flex items-center gap-2 font-semibold">
            <img src="/forkfix-mark.svg" alt="" width={20} height={20} />
            Forkfix
          </p>
          <p className="mt-3 max-w-[34ch] text-muted">
            A solo entry to the Nebius × NVIDIA Global AI Hackathon, Coding &amp; Agentic Engineering.
          </p>
        </div>
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_200px]">
          <div className="min-w-0">
            <h2 className="font-semibold">Rebuild these numbers</h2>
            <p className="mt-2 max-w-[56ch] text-muted">
              Every figure above comes from saved run reports. These two commands regenerate the totals and this
              page's run data from those reports. They spend no tokens and start no sandbox.
            </p>
            <pre className="mt-4 overflow-x-auto rounded-md border border-rule bg-panel p-4 font-mono text-[13px] leading-[1.7]">
              {`cd backend\n.\\.venv\\Scripts\\python.exe -m forkfix.report\n.\\.venv\\Scripts\\python.exe -m forkfix.viewer_data`}
            </pre>
          </div>
          <ul>
            <li>
              <a className={LINK} href={REPO_URL}>
                GitHub repository
              </a>
            </li>
            <li>
              <a className={LINK} href="https://www.swebench.com/">
                SWE-bench Lite
              </a>
            </li>
            <li>
              <a className={LINK} href="https://nebius.com/">
                Nebius Sandbox
              </a>
            </li>
            <li>
              <a className={LINK} href="https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/">
                NVIDIA Nemotron
              </a>
            </li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
