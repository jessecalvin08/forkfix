import { useEffect, useState } from "react";

import Hero from "./Hero";
import Method from "./Method";
import RealIssues from "./RealIssues";
import Replay, { type Route } from "./Replay";
import Result from "./Result";
import { ForkMark } from "./shared";
import { MODES, type IndexRow, type ModeName, type RunIndex } from "./types";

const REPO_URL = "https://github.com/jessecalvin08/forkfix";

const NAV = [
  { id: "result", label: "Result" },
  { id: "replay", label: "Replay" },
  { id: "real-issues", label: "Real issues" },
  { id: "method", label: "Method" },
] as const;

function readHash(): Partial<Route> {
  const [task, mode, node] = decodeURIComponent(location.hash.slice(1)).split("/");
  return {
    task: task || undefined,
    mode: MODES.includes(mode as ModeName) ? (mode as ModeName) : undefined,
    node: node || null,
  };
}

/** The branching-only win with the widest tree: the clearest first thing to show. */
function pickDefault(rows: IndexRow[]): string {
  const wins = rows.filter((r) => r.modes.branching.solved && !r.modes.matched.solved && !r.modes.linear.solved);
  wins.sort((a, b) => b.modes.branching.branches - a.modes.branching.branches);
  return (wins[0] ?? rows[0]).task;
}

export default function App() {
  const [index, setIndex] = useState<RunIndex | null>(null);
  const [failed, setFailed] = useState(false);
  const [route, setRoute] = useState<Route | null>(null);
  const [featured, setFeatured] = useState<string | null>(null);

  useEffect(() => {
    fetch("/runs/index.json", { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: RunIndex) => {
        setIndex(data);
        const hash = readHash();
        const known = data.rows.some((r) => r.task === hash.task);
        const def = pickDefault(data.rows);
        setFeatured(def);
        setRoute({
          task: known ? hash.task! : def,
          mode: hash.mode ?? "branching",
          node: known ? (hash.node ?? null) : null,
        });
      })
      .catch(() => setFailed(true));
  }, []);

  // Keep the URL shareable, but only once someone has opened a run: the bare URL stays clean.
  const [touched, setTouched] = useState(() => Boolean(readHash().task));
  useEffect(() => {
    if (!route || !touched) return;
    const hash = `#${route.task}/${route.mode}${route.node ? `/${route.node}` : ""}`;
    if (location.hash !== hash) history.replaceState(null, "", hash);
  }, [route, touched]);

  const open = (task: string, node?: string) => {
    setTouched(true);
    setRoute({ task, mode: "branching", node: node ?? null });
    requestAnimationFrame(() => document.getElementById("replay")?.scrollIntoView({ block: "start" }));
  };

  return (
    <div className="shell" id="top">
      <a className="skip-link" href="#replay">Skip to the run replay</a>
      <Header />
      <main>
        {failed && <p className="load-error" role="alert">The run data did not load. Reload the page to try again.</p>}
        {!index && !failed && <div className="wrap"><div className="skeleton hero-skel" aria-busy="true" aria-label="Loading results" /></div>}
        {index && route && featured && (
          <>
            <Hero index={index} featured={featured} onOpen={open} />
            <Result index={index} onOpen={open} />
            <Replay
              index={index}
              route={route}
              setRoute={(r) => {
                setTouched(true);
                setRoute(r);
              }}
            />
            <RealIssues />
          </>
        )}
        <Method />
      </main>
      <footer className="footer">
        <div className="wrap footer-grid">
          <p>
            Forkfix, a solo entry to the Nebius × NVIDIA Global AI Hackathon (Coding &amp; Agentic Engineering). Every
            number on this page is generated from saved run reports by <code>forkfix.report</code> and{" "}
            <code>forkfix.viewer_data</code>.
          </p>
          <a href={REPO_URL}>Source on GitHub ↗</a>
        </div>
      </footer>
    </div>
  );
}

function Header() {
  const [active, setActive] = useState<string>("");
  useEffect(() => {
    const els = NAV.map((n) => document.getElementById(n.id)).filter((e): e is HTMLElement => !!e);
    if (!els.length) return;
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (hit) setActive(hit.target.id);
      },
      { rootMargin: "-30% 0px -60% 0px", threshold: [0, 0.01] },
    );
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  });
  return (
    <header className="topbar">
      <div className="wrap topbar-in">
        <a className="wordmark" href="#top" aria-label="Forkfix, top of page">
          <ForkMark /> Forkfix
        </a>
        <nav aria-label="Sections">
          <ul>
            {NAV.map((n) => (
              <li key={n.id}>
                <a href={`#${n.id}`} aria-current={active === n.id ? "location" : undefined}>
                  {n.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <a className="topbar-link" href={REPO_URL}>
          GitHub ↗
        </a>
      </div>
    </header>
  );
}
